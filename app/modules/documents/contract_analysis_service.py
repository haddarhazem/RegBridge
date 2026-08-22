from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.ai.schemas import AgentRunRequestTrace, AgentRunResponseTrace, ModelTraceMetadata, TraceResourceRef, TraceSourceRef
from app.modules.ai.services import AgentRunService, _safe_error_message
from app.modules.documents.authorization import DocumentAuthorizationPolicy
from app.modules.documents.contract_analysis import ContractExtractionError, ContractExtractor
from app.modules.documents.contract_analysis_models import ContractAnalysis, ContractFinding
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import ProjectMember


class ContractAnalysisService:
    STRATEGY = "v2_structured_evidence"
    PROMPT_VERSION = "scrum193-contract-v2-evidence-v1"

    def __init__(self, session: AsyncSession, provider=None) -> None:
        self.session = session
        self.provider = provider
        self.policy = DocumentAuthorizationPolicy()

    async def _authorized_version(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID, version_id: uuid.UUID) -> tuple[Document, DocumentVersion]:
        document = await self.session.scalar(select(Document).where(Document.id == document_id, Document.deleted_at.is_(None)))
        if document is None or document.project_id is None:
            raise HTTPException(status_code=404, detail="Document not found")
        membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == document.project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
        if not self.policy.can_read(document.visibility, document.classification, membership, document.owner_user_id, actor.user_id):
            raise HTTPException(status_code=404, detail="Document not found")
        version = await self.session.scalar(select(DocumentVersion).where(DocumentVersion.id == version_id, DocumentVersion.document_id == document.id))
        if version is None or version.malware_scan_status != "clean":
            raise HTTPException(status_code=403, detail="Document version is not available")
        if not version.extracted_text:
            raise HTTPException(status_code=409, detail="Document version text is not available for analysis")
        return document, version

    async def _analysis_for_actor(self, actor: AuthenticatedPrincipal, analysis_id: uuid.UUID) -> ContractAnalysis:
        analysis = await self.session.scalar(select(ContractAnalysis).options(selectinload(ContractAnalysis.findings)).where(ContractAnalysis.id == analysis_id))
        if analysis is None:
            raise HTTPException(status_code=404, detail="Contract analysis not found")
        document = await self.session.scalar(select(Document).where(Document.id == analysis.document_id, Document.deleted_at.is_(None)))
        membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == analysis.project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
        if document is None or not self.policy.can_read(document.visibility, document.classification, membership, document.owner_user_id, actor.user_id):
            raise HTTPException(status_code=404, detail="Contract analysis not found")
        return analysis

    async def analyze(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID, version_id: uuid.UUID) -> ContractAnalysis:
        document, version = await self._authorized_version(actor, document_id, version_id)
        if self.session.in_transaction():
            await self.session.commit()
        analysis = ContractAnalysis(project_id=document.project_id, document_id=document.id, document_version_id=version.id, strategy=self.STRATEGY, prompt_version=self.PROMPT_VERSION, status="running", created_by_user_id=actor.user_id)
        self.session.add(analysis)
        await self.session.commit()
        request_id = uuid.uuid4()
        trace = AgentRunService(self.session)
        run = await trace.create_run(
            request_id=request_id,
            agent_name="contract-analyzer",
            capability="contract_analysis",
            user_id=actor.user_id,
            subject_type="document",
            subject_id=document.id,
            prompt_version=self.PROMPT_VERSION,
            request_payload=AgentRunRequestTrace(intent="contract_analysis", configuration_version=self.PROMPT_VERSION, context_refs=[TraceResourceRef(resource_type="document", resource_id=document.id, version_id=version.id)]),
            model_metadata=ModelTraceMetadata(temperature=0, max_output_tokens=1800, response_format="ContractExtractionOutput"),
        )
        await trace.start_run(run.id)
        analysis.agent_run_id = run.id
        await self.session.commit()
        try:
            provider = self.provider or get_mistral_provider()
            output, execution = await ContractExtractor(provider).extract(text=version.extracted_text, document_version_id=version.id)
            async with self.session.begin():
                analysis = await self.session.scalar(select(ContractAnalysis).where(ContractAnalysis.id == analysis.id).with_for_update())
                if analysis is None:
                    raise HTTPException(status_code=404, detail="Contract analysis not found")
                analysis.status = "completed"
                if execution is not None:
                    analysis.provider = execution.provider
                    analysis.model = execution.model or execution.logical_model
                for index, finding in enumerate(output.findings, 1):
                    evidence = finding.evidence[0]
                    self.session.add(ContractFinding(analysis_id=analysis.id, finding_index=index, finding_type="UNCERTAINTY", category=f"suggested_{finding.category}"[:80], statement=evidence.quote, risk_level=None, recommendation=None, uncertainty="Semantic interpretation withheld; source excerpt only.", evidence_document_version_id=evidence.document_version_id, evidence_quote=evidence.quote, evidence_start_char=evidence.start_char, evidence_end_char=evidence.end_char))
            await trace.succeed_run(run.id, AgentRunResponseTrace(summary="Contract analysis completed", result={"finding_count": len(output.findings)}, source_refs=[TraceSourceRef(source_id=str(version.id), knowledge_document_id=document.id, locator="document_version")]))
        except Exception as exc:
            await self.session.rollback()
            async with self.session.begin():
                analysis = await self.session.scalar(select(ContractAnalysis).where(ContractAnalysis.id == analysis.id).with_for_update())
                if analysis is not None:
                    analysis.status = "failed"
                    analysis.error_code = "contract_analysis_failed"
                    analysis.error_message = _safe_error_message(str(exc))
            await trace.fail_run(run.id, error_code="contract_analysis_failed", error_message=str(exc))
        return await self._analysis_for_actor(actor, analysis.id)

    async def get(self, actor: AuthenticatedPrincipal, analysis_id: uuid.UUID) -> ContractAnalysis:
        return await self._analysis_for_actor(actor, analysis_id)

    async def list_for_document(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID) -> list[ContractAnalysis]:
        document = await self.session.scalar(select(Document).where(Document.id == document_id, Document.deleted_at.is_(None)))
        if document is None or document.project_id is None:
            raise HTTPException(status_code=404, detail="Document not found")
        membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == document.project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
        if not self.policy.can_read(document.visibility, document.classification, membership, document.owner_user_id, actor.user_id):
            raise HTTPException(status_code=404, detail="Document not found")
        return list((await self.session.scalars(select(ContractAnalysis).options(selectinload(ContractAnalysis.findings)).where(ContractAnalysis.document_id == document.id).order_by(ContractAnalysis.created_at, ContractAnalysis.id))).all())
