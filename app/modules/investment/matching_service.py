from __future__ import annotations

import uuid
from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.llm import LLMProvider
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.matching import deterministic_match
from app.modules.investment.matching_models import MatchingRun
from app.modules.investment.matching_verification import explain_with_fallback, safe_explanation
from app.modules.investment.models import InvestorProfile, InvestorThesisVersion
from app.modules.projects.models import Project
from app.modules.projects.profile_models import StartupProfile, StartupProfileRevision
from app.modules.sharing.models import InvestorShareGrant


class MatchingService:
    def __init__(self, session: AsyncSession, provider: LLMProvider | None = None) -> None:
        self.session = session
        self.provider = provider

    async def _thesis(self, actor: AuthenticatedPrincipal, version_id: uuid.UUID | None) -> InvestorThesisVersion:
        profile = await self.session.scalar(select(InvestorProfile).where(InvestorProfile.user_id == actor.user_id))
        if profile is None:
            raise HTTPException(status_code=403, detail="Investor profile required")
        if version_id is None:
            version_id = profile.current_version_id
        version = await self.session.scalar(select(InvestorThesisVersion).where(InvestorThesisVersion.id == version_id, InvestorThesisVersion.investor_profile_id == profile.id))
        if version is None:
            raise HTTPException(status_code=404, detail="Investor thesis version not found")
        return version

    async def _startup_snapshot(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> tuple[Project, StartupProfileRevision | None, dict]:
        project = await self.session.scalar(select(Project).where(Project.id == project_id, Project.project_type.in_(["startup_in_creation", "existing_startup"])))
        if project is None:
            raise HTTPException(status_code=404, detail="Startup not found")
        profile = await self.session.scalar(select(StartupProfile).where(StartupProfile.project_id == project.id))
        revision = None
        shared = False
        if profile is not None and profile.current_revision:
            revision = await self.session.scalar(select(StartupProfileRevision).where(StartupProfileRevision.profile_id == profile.id, StartupProfileRevision.revision_number == profile.current_revision))
            if revision is not None:
                shared = await self.session.scalar(select(InvestorShareGrant.id).where(InvestorShareGrant.project_id == project.id, InvestorShareGrant.recipient_user_id == actor.user_id, InvestorShareGrant.resource_type == "STARTUP_PROFILE_REVISION", InvestorShareGrant.resource_id == revision.id, InvestorShareGrant.status == "ACTIVE", InvestorShareGrant.scope == "READ")) is not None
        if project.visibility != "public" and not shared:
            raise HTTPException(status_code=404, detail="Authorized startup snapshot not found")
        public = project.visibility == "public"
        fields = revision.snapshot if revision is not None else []
        allowed = {item.get("field_name"): item.get("value") for item in fields if item.get("visibility") == ("PUBLIC" if public else "INVESTOR_SHARED")}
        snapshot = {
            "project_id": str(project.id),
            "profile_revision_id": str(revision.id) if revision is not None else None,
            "sector": project.sector if public else None,
            "stage": project.current_progress if public else None,
            "geography": project.location if public else None,
            "technology": project.technology if public else None,
            "funding_need": allowed.get("fundraising_target"),
            "fields": allowed,
        }
        return project, revision, snapshot

    @staticmethod
    def _investor_snapshot(version: InvestorThesisVersion) -> dict:
        return {"thesis_version_id": str(version.id), "sectors": version.sectors, "stages": version.stages, "geographies": version.geographies, "technologies": version.technologies, "ticket_min": float(version.ticket_min) if version.ticket_min is not None else None, "ticket_max": float(version.ticket_max) if version.ticket_max is not None else None, "ticket_currency": version.ticket_currency}

    @staticmethod
    def _report(result: dict) -> dict:
        dimensions = result["dimensions"]
        return {"summary": "Preliminary structured compatibility report based only on available authorized data.", "strengths": [key for key, value in dimensions.items() if value == "MATCH"], "gaps": [key for key, value in dimensions.items() if value == "MISMATCH"], "unknowns": result["unknown_dimensions"], "caveats": ["This is not financial advice and does not predict startup success, returns, valuation, profitability, or investment safety.", "UNKNOWN dimensions were not inferred and were excluded from the score."], "deterministic_result": result}

    async def create(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, version_id: uuid.UUID | None = None) -> MatchingRun:
        version = await self._thesis(actor, version_id)
        _, revision, startup = await self._startup_snapshot(actor, project_id)
        investor = self._investor_snapshot(version)
        result = deterministic_match(investor, startup)
        if self.provider is None:
            explanation = safe_explanation(result)
            accepted = False
            execution: dict = {}
        else:
            verification = await explain_with_fallback(self.provider, investor_snapshot=investor, startup_snapshot=startup, result=result)
            explanation = verification.explanation
            accepted = verification.accepted
            execution = verification.execution or {}
        report = {**explanation.model_dump(mode="json"), "deterministic_result": result}
        run = MatchingRun(investor_user_id=actor.user_id, investor_thesis_version_id=version.id, startup_project_id=project_id, startup_snapshot_revision_id=revision.id if revision else None, investor_snapshot=investor, startup_snapshot=startup, matching_method=result["matching_method"], matching_method_version=result["matching_method_version"], score=result["score"], score_formula=result["score_formula"], dimensions=result["dimensions"], report=report, explanation_mode="llm" if accepted else "deterministic_fallback", llm_provider=execution.get("provider") if execution else ("mistral" if self.provider is not None else None), llm_model=execution.get("model") if execution else getattr(self.provider, "model", None), prompt_version=execution.get("prompt_version") if execution else ("scrum203-matching-explanation-v1" if self.provider is not None else None))
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID) -> MatchingRun:
        run = await self.session.scalar(select(MatchingRun).where(MatchingRun.id == run_id, MatchingRun.investor_user_id == actor.user_id))
        if run is None:
            raise HTTPException(status_code=404, detail="Matching run not found")
        return run
