"""Versioned regulatory assessment orchestration over trusted project snapshots."""

from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.context import AuthorizedContextBuilder, ProjectAuthorizationService
from app.modules.ai.contracts import OrchestrationRequest
from app.modules.ai.agents import AgentRegistry
from app.modules.ai.llm import LLMConfigurationError
from app.modules.ai.orchestration import DeterministicIntentClassifier, Orchestrator, Router
from app.modules.ai.services import AgentRunService
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.projects.repositories import ProjectContextRepository
from app.modules.regulatory.agent import RegulatoryAgent
from app.modules.regulatory.assessment_contracts import AssessmentConclusion, AssessmentResult
from app.modules.regulatory.assessment_models import AssessmentInputSnapshot, RegulatoryAssessment
from app.modules.regulatory.retrieval import RegulatoryConfigurationError, RegulatoryRetrievalError, get_regulatory_retriever
from app.modules.regulatory.agent import _unique_organizations
from app.modules.ai.providers.mistral import get_mistral_provider


class RegulatoryAssessmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _authorize(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> Project:
        project = await self.session.scalar(select(Project).where(Project.id == project_id))
        membership = await self.session.scalar(select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == actor.user_id,
            ProjectMember.status == "active",
        ))
        if project is None or membership is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    async def _trusted_snapshot_payload(self, project: Project) -> list[dict]:
        confirmed = project.confirmed_fields or {}
        declared_fields = {
            "activity": project.activity,
            "sector": project.sector,
            "technology": project.technology,
            "data": project.data_context,
            "market": project.target_market,
            "location": project.location,
        }
        payload: list[dict] = []
        for domain, value in declared_fields.items():
            if confirmed.get(domain) == "confirmed" and value:
                payload.append({"fact_id": None, "domain": domain, "value": value, "origin": "user_declared", "status": "confirmed"})
        rows = await self.session.scalars(select(ProjectFact).where(
            ProjectFact.project_id == project.id,
            ProjectFact.status.in_(["confirmed", "corrected"]),
        ).order_by(ProjectFact.created_at, ProjectFact.id))
        for fact in rows:
            payload.append({
                "fact_id": str(fact.id),
                "domain": fact.domain,
                "value": fact.value,
                "origin": fact.origin,
                "status": fact.status,
                "provenance": {"source_field": (fact.provenance or {}).get("source_field"), "source_rule": (fact.provenance or {}).get("source_rule")},
            })
        return payload

    async def _create_snapshot(self, project: Project) -> AssessmentInputSnapshot:
        facts = await self._trusted_snapshot_payload(project)
        canonical = json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        snapshot = AssessmentInputSnapshot(project_id=project.id, facts=facts, snapshot_hash=hashlib.sha256(canonical.encode()).hexdigest())
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    @staticmethod
    def _question(question: str, facts: list[dict]) -> str:
        context = "\n".join(f"{item['domain']}: {item['value']}" for item in facts) or "Aucun fait confirmé n'est disponible."
        return f"{question}\n\nFAITS CONFIRMÉS DU PROJET (instantané immuable)\n{context}"

    def _orchestrator(self) -> Orchestrator:
        repository = ProjectContextRepository(self.session)
        return Orchestrator(
            classifier=DeterministicIntentClassifier(),
            router=Router(AgentRegistry([RegulatoryAgent(retriever=get_regulatory_retriever(), provider=get_mistral_provider())])),
            context_builder=AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository)),
            agent_run_service=AgentRunService(self.session),
        )

    @staticmethod
    def _result_payload(agent_result) -> tuple[AssessmentResult, list[dict]]:
        evidence = [dict(item) for item in agent_result.evidence]
        sources = list(agent_result.sources)
        verdict = agent_result.structured_payload.get("verification_verdict")
        warnings = list(agent_result.warnings)
        obligations = [AssessmentConclusion(conclusion_id=f"obligation-{index}", statement=value, category="obligation", source_refs=[str(item.get("point_id")) for item in evidence]) for index, value in enumerate(agent_result.findings, 1)]
        recommendations = [AssessmentConclusion(conclusion_id=f"recommendation-{index}", statement=value, category="recommendation", source_refs=[str(item.get("point_id")) for item in evidence]) for index, value in enumerate(agent_result.recommendations, 1)]
        uncertainties = [AssessmentConclusion(conclusion_id=f"uncertainty-{index}", statement=value, category="uncertainty", source_refs=[]) for index, value in enumerate(agent_result.missing_information, 1)]
        if verdict != "pass":
            offset = len(uncertainties)
            uncertainties.extend(AssessmentConclusion(conclusion_id=f"uncertainty-{offset + index}", statement=value, category="uncertainty") for index, value in enumerate(warnings[:10], 1))
        return AssessmentResult(answer=agent_result.answer or "", obligations=obligations, recommendations=recommendations, uncertainties=uncertainties, sources=sources), evidence

    async def generate(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, question: str) -> RegulatoryAssessment:
        project = await self._authorize(actor, project_id)
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            project = await self._authorize(actor, project_id)
            snapshot = await self._create_snapshot(project)
        try:
            orchestrator = self._orchestrator()
            outcome = await orchestrator.run(OrchestrationRequest(
                question=self._question(question, snapshot.facts),
                principal=actor,
                intent_hint="regulatory",
                locale="fr",
            ))
        except (RegulatoryConfigurationError, RegulatoryRetrievalError, LLMConfigurationError):
            outcome = None
        if outcome and outcome.results:
            result, evidence = self._result_payload(outcome.results[0])
            payload = outcome.results[0]
            verdict = payload.structured_payload.get("verification_verdict")
            status = "blocked" if verdict == "block" else "completed"
            agent_run_id = payload.run_id
            reasons = [str(value) for value in payload.warnings]
        else:
            result = AssessmentResult(uncertainties=[AssessmentConclusion(conclusion_id="uncertainty-1", statement="L'évaluation n'a pas pu être générée de manière fiable.", category="uncertainty")])
            evidence = []
            verdict = "block"
            status = "failed"
            agent_run_id = None
            reasons = ["Regulatory generation unavailable"]
        async with self.session.begin():
            locked_project = await self.session.scalar(select(Project).where(Project.id == project_id).with_for_update())
            if locked_project is None:
                raise HTTPException(status_code=404, detail="Project not found")
            version = (await self.session.scalar(select(func.max(RegulatoryAssessment.version)).where(RegulatoryAssessment.project_id == project_id)) or 0) + 1
            assessment = RegulatoryAssessment(
                project_id=project_id,
                version=version,
                snapshot_id=snapshot.id,
                status=status,
                result=result.model_dump(mode="json"),
                source_provenance=evidence,
                verification_verdict=str(verdict) if verdict is not None else None,
                verification_reasons=reasons,
                agent_run_id=agent_run_id,
            )
            self.session.add(assessment)
            await self.session.flush()
        return assessment

    async def latest(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> RegulatoryAssessment | None:
        await self._authorize(actor, project_id)
        return await self.session.scalar(select(RegulatoryAssessment).where(RegulatoryAssessment.project_id == project_id).order_by(RegulatoryAssessment.version.desc()).limit(1))

    async def list_versions(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> list[RegulatoryAssessment]:
        await self._authorize(actor, project_id)
        return list((await self.session.scalars(select(RegulatoryAssessment).where(RegulatoryAssessment.project_id == project_id).order_by(RegulatoryAssessment.version))).all())

    async def get_version(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, version: int) -> RegulatoryAssessment:
        await self._authorize(actor, project_id)
        assessment = await self.session.scalar(select(RegulatoryAssessment).where(RegulatoryAssessment.project_id == project_id, RegulatoryAssessment.version == version))
        if assessment is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return assessment
