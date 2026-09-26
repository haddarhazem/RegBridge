"""Authorization and persistence boundary for contract analysis."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.ai.schemas import AgentRunRequestTrace, AgentRunResponseTrace, TraceResourceRef, TraceSourceRef
from app.modules.ai.services import AgentRunService, _safe_error_message
from app.modules.documents.authorization import DocumentAuthorizationPolicy
from app.core.config import Settings, get_settings
from app.modules.ai.providers.selection import get_llm_provider
from app.modules.documents.contract_analysis import ClauseAnalysis, ContractAnalyzer, ContractExtractionError, extract_parties, segment_contract_text
from app.modules.documents.contract_analysis_models import ContractAnalysis, ContractClause
from app.modules.documents.contract_semantic import (
    ContractSemanticAnalyzer,
    ContractSemanticFailure,
    SemanticClauseDraft,
    SemanticEvidenceClaim,
    ProviderContractSemanticAnalyzer,
    build_verified_semantic_output,
)
from app.modules.documents.extraction import extraction_status
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import ProjectMember


class ContractAnalysisService:
    """Analyze a clean, immutable document version for an active project member."""

    STRATEGY = "v4_document_first_semantic_evidence"
    ANALYSIS_VERSION = 2

    def __init__(self, session: AsyncSession, provider=None, analyzer: ContractAnalyzer | None = None, semantic_analyzer: ContractSemanticAnalyzer | None = None, settings: Settings | None = None) -> None:
        self.session = session
        # ``provider`` is accepted only to keep the old construction seam
        # stable. Contract text is not sent to a third-party model by this
        # V1 analyser.
        self.provider = provider
        self.analyzer = analyzer or ContractAnalyzer()
        self.semantic_analyzer = semantic_analyzer
        self.settings = settings or get_settings()
        self.policy = DocumentAuthorizationPolicy()

    def _configured_semantic_analyzer(self) -> ContractSemanticAnalyzer | None:
        if self.semantic_analyzer is not None:
            return self.semantic_analyzer
        if not (self.settings.document_external_processing_enabled and self.settings.contract_external_semantic_analysis_enabled):
            return None
        return ProviderContractSemanticAnalyzer(self.provider or get_llm_provider())

    @staticmethod
    def _source_method(version) -> str:
        metadata = version.extraction_metadata if isinstance(version.extraction_metadata, dict) else {}
        extraction = metadata.get("extraction") if isinstance(metadata.get("extraction"), dict) else {}
        page_methods = {
            str(value).upper()
            for value in extraction.get("page_methods", [])
            if isinstance(value, str)
        }
        # Page-level provenance is authoritative when it is available.  The
        # worker emits this for hybrid PDF extraction, whereas historical
        # versions have only their overall extraction method.
        if "OCR" in page_methods and "NATIVE" in page_methods:
            return "MIXED"
        if "OCR" in page_methods:
            return "OCR"
        method = str(extraction.get("method") or "").casefold()
        if "ocr" in method and "native" in method:
            return "MIXED"
        return "OCR" if "ocr" in method else "NATIVE"

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
        if extraction_status(version) != "ready" or not version.extracted_text:
            raise HTTPException(status_code=409, detail="Document version text is not available for analysis")
        return document, version

    async def _analysis_for_actor(self, actor: AuthenticatedPrincipal, analysis_id: uuid.UUID) -> ContractAnalysis:
        analysis = await self.session.scalar(
            select(ContractAnalysis)
            .options(selectinload(ContractAnalysis.clauses))
            .where(ContractAnalysis.id == analysis_id)
        )
        if analysis is None:
            raise HTTPException(status_code=404, detail="Contract analysis not found")
        version = await self.session.get(DocumentVersion, analysis.document_version_id)
        document = await self.session.get(Document, version.document_id) if version is not None else None
        membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == analysis.project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
        if document is None or document.deleted_at is not None or not self.policy.can_read(document.visibility, document.classification, membership, document.owner_user_id, actor.user_id):
            raise HTTPException(status_code=404, detail="Contract analysis not found")
        # Response serialization needs the document reference while V2.1 keeps
        # only the immutable version foreign key on the analysis row.
        analysis._response_document_id = document.id
        return analysis

    async def analyze(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID, version_id: uuid.UUID) -> ContractAnalysis:
        document, version = await self._authorized_version(actor, document_id, version_id)
        current = await self.session.scalar(
            select(func.max(ContractAnalysis.analysis_version)).where(ContractAnalysis.document_version_id == version.id)
        )
        analysis = ContractAnalysis(
            project_id=document.project_id,
            document_version_id=version.id,
            analysis_version=(current or 0) + 1,
            overall_risk_level="unknown",
            recommendations=[],
            missing_context=[],
            verification_status="running",
        )
        self.session.add(analysis)
        await self.session.commit()

        trace = AgentRunService(self.session)
        run = await trace.create_run(
            request_id=uuid.uuid4(),
            agent_name="contract-analyzer",
            capability="contract_analysis",
            user_id=actor.user_id,
            subject_type="document",
            subject_id=document.id,
            prompt_version=self.STRATEGY,
            request_payload=AgentRunRequestTrace(
                intent="contract_analysis",
                configuration_version=self.STRATEGY,
                context_refs=[TraceResourceRef(resource_type="document", resource_id=document.id, version_id=version.id)],
            ),
        )
        await trace.start_run(run.id)
        analysis.agent_run_id = run.id
        await self.session.commit()
        analysis_id = analysis.id
        semantic_failure_category: str | None = None
        section_analysis_status = "completed"
        consistency_status = "completed"
        consistency_attempt_count: int | None = None
        consistency_latency_ms: float | None = None
        try:
            source_method = self._source_method(version)
            semantic = self._configured_semantic_analyzer()
            if semantic is None:
                output = self.analyzer.analyze(text=version.extracted_text, document_version_id=version.id, source_method=source_method)
            else:
                try:
                    sections = segment_contract_text(version.extracted_text, source_method=source_method)
                    semantic_result = await semantic.analyze(
                        sections=sections,
                        parties=extract_parties(sections),
                    )
                    output = build_verified_semantic_output(
                        text=version.extracted_text,
                        document_version_id=version.id,
                        source_method=source_method,
                        result=semantic_result,
                    )
                    if semantic_result.consistency_failure_category is not None:
                        semantic_failure_category = semantic_result.consistency_failure_category
                        consistency_status = "failed"
                        output.semantic_status = "partial"
                        output.missing_context = [
                            "Les constats de sections ont ete analyses, mais la comparaison de coherence inter-clauses n'a pas pu etre terminee."
                        ]
                    consistency_attempt_count = semantic_result.consistency_attempt_count
                    consistency_latency_ms = semantic_result.consistency_latency_ms
                except ContractSemanticFailure as exc:
                    semantic_failure_category = exc.category
                    section_analysis_status = "failed"
                    consistency_status = "failed"
                    output = self.analyzer.analyze(text=version.extracted_text, document_version_id=version.id, source_method=source_method)
                    output.missing_context = ["Analyse semantique indisponible; seuls la structure et les passages verifies sont affiches."]
            async with self.session.begin():
                persisted = await self.session.scalar(
                    select(ContractAnalysis)
                    .options(selectinload(ContractAnalysis.clauses))
                    .where(ContractAnalysis.id == analysis.id)
                    .with_for_update()
                )
                if persisted is None:
                    raise HTTPException(status_code=404, detail="Contract analysis not found")
                persisted.contract_type = output.contract_type
                persisted.overall_risk_level = output.overall_risk_level
                persisted.summary = output.summary
                persisted.recommendations = output.recommendations
                persisted.missing_context = self._analysis_metadata(
                    output,
                    semantic_failure_category=semantic_failure_category,
                    section_analysis_status=section_analysis_status,
                    consistency_status=consistency_status,
                    consistency_attempt_count=consistency_attempt_count,
                    consistency_latency_ms=consistency_latency_ms,
                    provider=getattr(self.provider or get_llm_provider(), "provider_name", None) if semantic is not None else None,
                    model=getattr(self.provider or get_llm_provider(), "model", None) if semantic is not None else None,
                )
                persisted.verification_status = output.semantic_status
                for index, clause in enumerate(output.clauses, 1):
                    self.session.add(self._clause_row(persisted.id, index, clause))
            await trace.succeed_run(
                run.id,
                AgentRunResponseTrace(
                    summary="Contract analysis completed" if output.semantic_status == "completed" else "Contract structure analysis partially completed",
                    result={
                        "clause_count": len(output.clauses),
                        "analysis_version": analysis.analysis_version,
                        "strategy": self.STRATEGY,
                        "semantic_status": output.semantic_status,
                        "semantic_failure_category": semantic_failure_category,
                        "consistency_stage": "contract_consistency" if semantic is not None else None,
                        "consistency_attempt_count": consistency_attempt_count,
                        "consistency_latency_ms": consistency_latency_ms,
                    },
                    source_refs=[TraceSourceRef(source_id=str(version.id), knowledge_document_id=document.id, locator="document_version")],
                ),
            )
        except Exception as exc:
            await self.session.rollback()
            async with self.session.begin():
                persisted = await self.session.scalar(select(ContractAnalysis).where(ContractAnalysis.id == analysis.id).with_for_update())
                if persisted is not None:
                    persisted.verification_status = "failed"
                    persisted.missing_context = ["L'analyse n'a pas pu être terminée. Relancez-la après avoir vérifié l'extraction du document."]
            await trace.fail_run(run.id, error_code="contract_analysis_failed", error_message=_safe_error_message(str(exc)))
        self.session.expire_all()
        return await self._analysis_for_actor(actor, analysis_id)

    @staticmethod
    def _analysis_metadata(
        output,
        *,
        semantic_failure_category: str | None = None,
        section_analysis_status: str = "completed",
        consistency_status: str = "completed",
        consistency_attempt_count: int | None = None,
        consistency_latency_ms: float | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> list:
        metadata = {
            "parties": output.parties,
            "party_details": [item.model_dump(mode="json") for item in output.party_details],
            "effective_dates": output.effective_dates,
            "missing_context": output.missing_context,
            "section_analysis_status": section_analysis_status,
            "consistency_status": consistency_status,
            "consistency_stage": "contract_consistency",
            "consistency_attempt_count": consistency_attempt_count,
            "consistency_latency_ms": consistency_latency_ms,
            "consistency_provider": provider,
            "consistency_model": model,
        }
        if semantic_failure_category is not None:
            metadata["semantic_failure_category"] = semantic_failure_category
        return [metadata]

    @staticmethod
    def _clause_row(analysis_id: uuid.UUID, order: int, clause: ClauseAnalysis) -> ContractClause:
        source_refs = {
            "evidence": [item.model_dump(mode="json") for item in clause.evidence],
            "analysis": clause.model_dump(mode="json", exclude={"evidence", "source_text"}),
        }
        return ContractClause(
            contract_analysis_id=analysis_id,
            clause_order=order,
            clause_type=clause.clause_type,
            heading=clause.title,
            extracted_text=clause.source_text,
            risk_level=clause.risk_level,
            finding="\n".join(clause.issues) or clause.plain_language_summary,
            recommendation=clause.recommendation,
            source_refs=source_refs,
            confidence=clause.confidence,
        )

    async def get(self, actor: AuthenticatedPrincipal, analysis_id: uuid.UUID) -> ContractAnalysis:
        return await self._analysis_for_actor(actor, analysis_id)

    @staticmethod
    def _persisted_section_drafts(clauses: list[ContractClause]) -> list[SemanticClauseDraft]:
        """Rehydrate only bounded persisted section projections for a retry."""
        drafts: list[SemanticClauseDraft] = []
        for clause in clauses:
            refs = clause.source_refs if isinstance(clause.source_refs, dict) else {}
            detail = refs.get("analysis") if isinstance(refs.get("analysis"), dict) else {}
            section_id = detail.get("section_id")
            status = detail.get("status")
            if not isinstance(section_id, str) or not section_id or status == "MISSING" or section_id.startswith("consistency-"):
                continue
            evidence = []
            for item in refs.get("evidence", []):
                if not isinstance(item, dict) or item.get("verification_status") != "VERIFIED":
                    continue
                quote = item.get("quote")
                evidence_section = item.get("section_id")
                if isinstance(quote, str) and isinstance(evidence_section, str):
                    evidence.append(SemanticEvidenceClaim(section_id=evidence_section, quote=quote))
            drafts.append(SemanticClauseDraft(
                section_id=section_id,
                clause_type=str(clause.clause_type or "other"),
                summary=str(detail.get("plain_language_summary") or clause.finding or "Section analysee."),
                status=status if status in {"FOUND", "AMBIGUOUS", "OTHER"} else "FOUND",
                risk_level=clause.risk_level if clause.risk_level in {"low", "medium", "high", "critical", "informational", "unknown"} else "unknown",
                issues=[str(value) for value in detail.get("issues", []) if isinstance(value, str)][:8],
                evidence_claims=evidence[:4],
            ))
        return drafts

    async def retry_consistency(self, actor: AuthenticatedPrincipal, analysis_id: uuid.UUID) -> ContractAnalysis:
        """Retry only global consistency from persisted, authorized sections."""
        analysis = await self._analysis_for_actor(actor, analysis_id)
        if analysis.verification_status != "partial":
            raise HTTPException(status_code=409, detail="Only a partial contract analysis can retry consistency")
        version = await self.session.get(DocumentVersion, analysis.document_version_id)
        document = await self.session.get(Document, version.document_id) if version is not None else None
        if version is None or document is None or not version.extracted_text:
            raise HTTPException(status_code=409, detail="Document version text is not available for consistency retry")
        semantic = self._configured_semantic_analyzer()
        if not isinstance(semantic, ProviderContractSemanticAnalyzer):
            raise HTTPException(status_code=409, detail="External semantic consistency is not enabled")
        sections = segment_contract_text(version.extracted_text, source_method=self._source_method(version))
        drafts = self._persisted_section_drafts(analysis.clauses)
        if not drafts:
            raise HTTPException(status_code=409, detail="No completed section findings are available for consistency retry")
        result = await semantic.analyze_consistency_only(drafts=drafts, sections=sections)
        metadata = analysis.missing_context[0] if isinstance(analysis.missing_context, list) and analysis.missing_context and isinstance(analysis.missing_context[0], dict) else {}
        metadata = dict(metadata)
        metadata["section_analysis_status"] = "completed"
        metadata["consistency_stage"] = "contract_consistency"
        metadata["consistency_provider"] = getattr(semantic.provider, "provider_name", None)
        metadata["consistency_model"] = getattr(semantic.provider, "model", None)
        metadata["consistency_attempt_count"] = result.consistency_attempt_count
        metadata["consistency_latency_ms"] = result.consistency_latency_ms
        if result.consistency_failure_category is not None:
            metadata["consistency_status"] = "failed"
            metadata["semantic_failure_category"] = result.consistency_failure_category
            metadata["missing_context"] = ["Les constats de sections sont termines, mais la verification de coherence globale n'a pas pu etre terminee."]
            analysis.missing_context = [metadata]
            await self.session.commit()
            return await self._analysis_for_actor(actor, analysis_id)

        candidate = build_verified_semantic_output(
            text=version.extracted_text,
            document_version_id=version.id,
            source_method=self._source_method(version),
            result=result,
        )
        existing_section_ids = {
            item.source_refs.get("analysis", {}).get("section_id")
            for item in analysis.clauses
            if isinstance(item.source_refs, dict) and isinstance(item.source_refs.get("analysis"), dict)
        }
        order = max((item.clause_order for item in analysis.clauses), default=0)
        for clause in candidate.clauses:
            if not clause.section_id.startswith("consistency-") or clause.section_id in existing_section_ids:
                continue
            order += 1
            self.session.add(self._clause_row(analysis.id, order, clause))
        metadata["consistency_status"] = "completed"
        metadata["semantic_failure_category"] = None
        metadata["missing_context"] = []
        analysis.missing_context = [metadata]
        analysis.verification_status = "completed"
        await self.session.commit()
        return await self._analysis_for_actor(actor, analysis_id)

    async def list_for_document(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID) -> list[ContractAnalysis]:
        document = await self.session.scalar(select(Document).where(Document.id == document_id, Document.deleted_at.is_(None)))
        if document is None or document.project_id is None:
            raise HTTPException(status_code=404, detail="Document not found")
        membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == document.project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
        if not self.policy.can_read(document.visibility, document.classification, membership, document.owner_user_id, actor.user_id):
            raise HTTPException(status_code=404, detail="Document not found")
        versions = select(DocumentVersion.id).where(DocumentVersion.document_id == document.id)
        analyses = list((await self.session.scalars(
            select(ContractAnalysis)
            .options(selectinload(ContractAnalysis.clauses))
            .where(ContractAnalysis.document_version_id.in_(versions))
            .order_by(ContractAnalysis.created_at, ContractAnalysis.id)
        )).all())
        for analysis in analyses:
            analysis._response_document_id = document.id
        return analyses
