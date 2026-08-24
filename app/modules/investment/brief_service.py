from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.llm import LLMProvider
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.brief_generation import (
    BRIEF_GENERATION_VERSION,
    BRIEF_PROMPT_VERSION,
    deterministic_missing_information,
    generate_with_fallback,
    public_content,
)
from app.modules.investment.brief_models import InvestorOpportunityBriefRun, InvestorOpportunityBriefVersion
from app.modules.investment.brief_semantic_verification import verify_semantically
from app.modules.investment.brief_verification import ClaimDecision, VERIFIER_STRATEGY, VERIFIER_VERSION, verify_frozen_brief
from app.modules.investment.brief_verification_models import BriefClaimVerification, BriefVerificationRun
from app.modules.investment.brief_verification_schemas import BriefVerificationResponse, ClaimVerificationResponse
from app.modules.investment.brief_schemas import BriefEvidenceBundle, BriefVersionCreate, BriefVersionResponse, OpportunityBriefContent
from app.modules.investment.matching_models import MatchingRun
from app.modules.investment.matching_service import MatchingService
from app.modules.projects.models import Project, ProjectFact


class OpportunityBriefService:
    def __init__(self, session: AsyncSession, provider: LLMProvider | None = None) -> None:
        self.session = session
        self.provider = provider

    async def _matching_run(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, version_id: uuid.UUID | None, matching_run_id: uuid.UUID | None) -> MatchingRun:
        if matching_run_id is not None:
            run = await self.session.scalar(select(MatchingRun).where(MatchingRun.id == matching_run_id, MatchingRun.investor_user_id == actor.user_id, MatchingRun.startup_project_id == project_id))
            if run is None or (version_id is not None and run.investor_thesis_version_id != version_id):
                raise HTTPException(status_code=404, detail="Authorized matching run not found")
            return run
        return await MatchingService(self.session).create(actor, project_id, version_id)

    async def _evidence_bundle(self, actor: AuthenticatedPrincipal, run: MatchingRun) -> BriefEvidenceBundle:
        project = await self.session.get(Project, run.startup_project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Startup not found")
        snapshot = copy.deepcopy(run.startup_snapshot)
        confirmed_fields = project.confirmed_fields or {}
        core_fields = {"sector": "sector", "stage": "current_progress", "geography": "location", "technology": "technology", "funding_need": "funding_need"}
        for key, confirmation_key in core_fields.items():
            if confirmation_key != "funding_need" and confirmed_fields.get(confirmation_key) != "confirmed":
                snapshot[key] = None
        facts = list((await self.session.scalars(select(ProjectFact).where(ProjectFact.project_id == project.id, ProjectFact.status.in_(["confirmed", "corrected"])).order_by(ProjectFact.created_at, ProjectFact.id))).all())
        confirmed_facts: list[dict] = []
        evidence_refs = [f"matching:{run.id}:{dimension}" for dimension in run.dimensions]
        for fact in facts:
            ref = f"project_fact:{fact.id}"
            evidence_refs.append(ref)
            confirmed_facts.append({"evidence_ref": ref, "fact_id": str(fact.id), "domain": fact.domain, "value": fact.value, "status": fact.status, "provenance": {"source_field": (fact.provenance or {}).get("source_field"), "rule": (fact.provenance or {}).get("rule")}})
        for field_name, value in (snapshot.get("fields") or {}).items():
            ref = f"startup_snapshot:{run.startup_snapshot.get('profile_revision_id')}:{field_name}"
            evidence_refs.append(ref)
            confirmed_facts.append({"evidence_ref": ref, "domain": field_name, "value": value, "status": "confirmed"})
        matching_result = {
            "matching_method": run.matching_method,
            "matching_method_version": run.matching_method_version,
            "score": float(run.score) if run.score is not None else None,
            "score_formula": run.score_formula,
            "dimensions": run.dimensions,
            "unknown_dimensions": [key for key, value in run.dimensions.items() if value == "UNKNOWN"],
        }
        missing = deterministic_missing_information(matching_result, confirmed_facts)
        return BriefEvidenceBundle(investor_thesis=run.investor_snapshot, startup_snapshot=snapshot, confirmed_facts=confirmed_facts[:50], matching_result=matching_result, missing_information=missing, evidence_refs=list(dict.fromkeys(evidence_refs)))

    async def create(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, version_id: uuid.UUID | None = None, matching_run_id: uuid.UUID | None = None) -> InvestorOpportunityBriefRun:
        matching = await self._matching_run(actor, project_id, version_id, matching_run_id)
        bundle = await self._evidence_bundle(actor, matching)
        generated, accepted, _, execution, _, _ = await generate_with_fallback(self.provider, bundle)
        content = public_content(generated, bundle.missing_information)
        run = InvestorOpportunityBriefRun(
            investor_user_id=actor.user_id,
            investor_thesis_version_id=matching.investor_thesis_version_id,
            startup_project_id=matching.startup_project_id,
            matching_run_id=matching.id,
            startup_snapshot_revision_id=matching.startup_snapshot_revision_id,
            investor_snapshot=bundle.investor_thesis,
            startup_snapshot=bundle.startup_snapshot,
            evidence_bundle=bundle.model_dump(mode="json"),
            matching_result=bundle.matching_result,
            generation_strategy="mistral_json_schema" if accepted else "deterministic_template",
            generation_version=BRIEF_GENERATION_VERSION,
            status="UNVERIFIED" if accepted else "DRAFT",
            content=content,
            provider=execution.get("provider") if execution else ("mistral" if self.provider else None),
            model=execution.get("model") if execution else getattr(self.provider, "model", None),
            prompt_version=execution.get("prompt_version") if execution else (BRIEF_PROMPT_VERSION if self.provider else None),
        )
        self.session.add(run)
        await self.session.flush()
        self.session.add(InvestorOpportunityBriefVersion(
            brief_run_id=run.id,
            version_number=1,
            author_user_id=actor.user_id,
            content=content,
            status=run.status,
            investor_thesis_version_id=matching.investor_thesis_version_id,
            startup_snapshot_revision_id=matching.startup_snapshot_revision_id,
            matching_run_id=matching.id,
            generation_strategy=run.generation_strategy,
            generation_version=run.generation_version,
            provider=run.provider,
            model=run.model,
            prompt_version=run.prompt_version,
        ))
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID) -> InvestorOpportunityBriefRun:
        run = await self.session.scalar(select(InvestorOpportunityBriefRun).where(InvestorOpportunityBriefRun.id == run_id, InvestorOpportunityBriefRun.investor_user_id == actor.user_id))
        if run is None:
            raise HTTPException(status_code=404, detail="Opportunity brief not found")
        return run

    async def _authorized_version(self, actor: AuthenticatedPrincipal, version_id: uuid.UUID, *, lock: bool = False) -> InvestorOpportunityBriefVersion:
        query = select(InvestorOpportunityBriefVersion).join(
            InvestorOpportunityBriefRun,
            InvestorOpportunityBriefRun.id == InvestorOpportunityBriefVersion.brief_run_id,
        ).where(
            InvestorOpportunityBriefVersion.id == version_id,
            InvestorOpportunityBriefRun.investor_user_id == actor.user_id,
        )
        if lock:
            query = query.with_for_update()
        version = await self.session.scalar(query)
        if version is None:
            raise HTTPException(status_code=404, detail="Opportunity brief version not found")
        return version

    async def current_version(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID) -> InvestorOpportunityBriefVersion:
        await self.get(actor, run_id)
        version = await self.session.scalar(select(InvestorOpportunityBriefVersion).where(InvestorOpportunityBriefVersion.brief_run_id == run_id).order_by(InvestorOpportunityBriefVersion.version_number.desc()).limit(1))
        if version is None:
            raise HTTPException(status_code=404, detail="Opportunity brief version not found")
        return version

    async def _verification_status(self, version: InvestorOpportunityBriefVersion) -> str:
        latest = await self.session.scalar(select(BriefVerificationRun).where(BriefVerificationRun.brief_version_id == version.id).order_by(BriefVerificationRun.created_at.desc(), BriefVerificationRun.id.desc()).limit(1))
        if latest is not None:
            return latest.status
        return version.status if version.status in {"VERIFIED", "VERIFICATION_FAILED", "APPROVED"} else "UNVERIFIED"

    async def version_response(self, version: InvestorOpportunityBriefVersion) -> BriefVersionResponse:
        public_content = {key: version.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")}
        return BriefVersionResponse(
            id=version.id,
            brief_run_id=version.brief_run_id,
            version_number=version.version_number,
            author_user_id=version.author_user_id,
            created_at=version.created_at,
            status=version.status,
            verification_status=await self._verification_status(version),
            approved=version.status == "APPROVED",
            approved_by_user_id=version.approved_by_user_id,
            approved_at=version.approved_at,
            investor_thesis_version_id=version.investor_thesis_version_id,
            startup_snapshot_revision_id=version.startup_snapshot_revision_id,
            matching_run_id=version.matching_run_id,
            generation_strategy=version.generation_strategy,
            generation_version=version.generation_version,
            provider=version.provider,
            model=version.model,
            prompt_version=version.prompt_version,
            content=OpportunityBriefContent.model_validate(public_content),
        )

    async def list_versions(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID) -> list[BriefVersionResponse]:
        await self.get(actor, run_id)
        versions = list((await self.session.scalars(select(InvestorOpportunityBriefVersion).where(InvestorOpportunityBriefVersion.brief_run_id == run_id).order_by(InvestorOpportunityBriefVersion.version_number))).all())
        return [await self.version_response(version) for version in versions]

    async def create_version(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID, data: BriefVersionCreate) -> BriefVersionResponse:
        parent = await self.get(actor, run_id)
        locked_parent = await self.session.scalar(select(InvestorOpportunityBriefRun).where(InvestorOpportunityBriefRun.id == parent.id, InvestorOpportunityBriefRun.investor_user_id == actor.user_id).with_for_update())
        if locked_parent is None:
            raise HTTPException(status_code=404, detail="Opportunity brief not found")
        public_content = data.content.model_dump(mode="json")
        prior_claims = locked_parent.content.get("claims", [])
        content = dict(public_content)
        content["claims"] = [
            {"text": text, "evidence_refs": (prior_claims[index].get("evidence_refs", []) if index < len(prior_claims) else [])}
            for index, text in enumerate(public_content.get("investment_highlights", []))
        ]
        latest_number = await self.session.scalar(select(func.max(InvestorOpportunityBriefVersion.version_number)).where(InvestorOpportunityBriefVersion.brief_run_id == run_id)) or 0
        version = InvestorOpportunityBriefVersion(
            brief_run_id=run_id,
            version_number=int(latest_number) + 1,
            author_user_id=actor.user_id,
            content=content,
            status="DRAFT",
            investor_thesis_version_id=locked_parent.investor_thesis_version_id,
            startup_snapshot_revision_id=locked_parent.startup_snapshot_revision_id,
            matching_run_id=locked_parent.matching_run_id,
            generation_strategy=locked_parent.generation_strategy,
            generation_version=locked_parent.generation_version,
            provider=locked_parent.provider,
            model=locked_parent.model,
            prompt_version=locked_parent.prompt_version,
        )
        self.session.add(version)
        locked_parent.status = "DRAFT"
        await self.session.commit()
        await self.session.refresh(version)
        return await self.version_response(version)

    async def approve_version(self, actor: AuthenticatedPrincipal, version_id: uuid.UUID) -> BriefVersionResponse:
        version = await self._authorized_version(actor, version_id, lock=True)
        if version.status == "APPROVED":
            return await self.version_response(version)
        if version.status != "VERIFIED":
            raise HTTPException(status_code=409, detail="Only an exactly verified version can be approved")
        verification = await self.session.scalar(select(BriefVerificationRun).where(BriefVerificationRun.brief_version_id == version.id, BriefVerificationRun.status == "VERIFIED").order_by(BriefVerificationRun.created_at.desc(), BriefVerificationRun.id.desc()).limit(1))
        if verification is None:
            raise HTTPException(status_code=409, detail="Exact version verification is required")
        version.status = "APPROVED"
        version.approved_by_user_id = actor.user_id
        version.approved_at = datetime.now(timezone.utc)
        current_id = await self.session.scalar(select(InvestorOpportunityBriefVersion.id).where(InvestorOpportunityBriefVersion.brief_run_id == version.brief_run_id).order_by(InvestorOpportunityBriefVersion.version_number.desc()).limit(1))
        parent = await self.session.get(InvestorOpportunityBriefRun, version.brief_run_id)
        if parent is not None and current_id == version.id:
            parent.status = "APPROVED"
        await self.session.commit()
        await self.session.refresh(version)
        return await self.version_response(version)

    async def verify(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID, version_id: uuid.UUID | None = None) -> BriefVerificationResponse:
        brief = await self.get(actor, run_id)
        version = await self.current_version(actor, run_id) if version_id is None else await self._authorized_version(actor, version_id)
        if version.brief_run_id != run_id:
            raise HTTPException(status_code=404, detail="Opportunity brief version not found")
        decisions = verify_frozen_brief(version.content, brief.evidence_bundle, brief.matching_result)
        semantic_provider = self.provider
        provider_metadata: dict = {}
        if any(decision.verdict == "UNVERIFIABLE" for decision in decisions) and semantic_provider is None:
            try:
                semantic_provider = get_mistral_provider()
            except Exception:
                semantic_provider = None
        if semantic_provider is not None:
            resolved: list[ClaimDecision] = []
            for decision in decisions:
                if decision.verdict != "UNVERIFIABLE":
                    resolved.append(decision)
                    continue
                evidence = {"confirmed_facts": [fact for fact in brief.evidence_bundle.get("confirmed_facts", []) if fact.get("evidence_ref") in decision.evidence_refs], "matching_result": {"dimensions": brief.matching_result.get("dimensions", {})}}
                semantic, execution, error = await verify_semantically(semantic_provider, claim=decision.claim_text, claim_type=decision.claim_type, evidence=evidence, evidence_refs=decision.evidence_refs)
                if execution:
                    provider_metadata = execution
                if semantic is None:
                    resolved.append(ClaimDecision(decision.claim_id, decision.section, decision.claim_text, decision.claim_type, "UNVERIFIABLE", "semantic_provider_unavailable" if error and error.startswith("provider_failure") else "semantic_output_rejected", decision.evidence_refs))
                else:
                    resolved.append(ClaimDecision(decision.claim_id, decision.section, decision.claim_text, decision.claim_type, semantic.status, f"semantic_{semantic.reason_code}", semantic.evidence_refs))
            decisions = resolved
        status = "VERIFIED" if decisions and all(decision.verdict == "SUPPORTED" for decision in decisions) else "VERIFICATION_FAILED"
        verification = BriefVerificationRun(
            brief_run_id=brief.id,
            brief_version_id=version.id,
            verifier_strategy=VERIFIER_STRATEGY,
            verifier_version=VERIFIER_VERSION,
            status=status,
            provider=provider_metadata.get("provider"),
            model=provider_metadata.get("model"),
            prompt_version=provider_metadata.get("prompt_version"),
        )
        self.session.add(verification)
        await self.session.flush()
        rows = [BriefClaimVerification(
            verification_run_id=verification.id,
            claim_id=decision.claim_id,
            section=decision.section,
            claim_text=decision.claim_text,
            claim_type=decision.claim_type,
            verdict=decision.verdict,
            reason_code=decision.reason_code,
            evidence_refs=decision.evidence_refs,
        ) for decision in decisions]
        self.session.add_all(rows)
        version.status = status
        if version.version_number == (await self.session.scalar(select(func.max(InvestorOpportunityBriefVersion.version_number)).where(InvestorOpportunityBriefVersion.brief_run_id == brief.id))):
            brief.status = status
        await self.session.commit()
        await self.session.refresh(verification)
        rows.sort(key=lambda row: str(row.id))
        return BriefVerificationResponse(
            id=verification.id,
            brief_run_id=brief.id,
            brief_version_id=version.id,
            verifier_strategy=verification.verifier_strategy,
            verifier_version=verification.verifier_version,
            status=verification.status,
            created_at=verification.created_at,
            claims=[ClaimVerificationResponse.model_validate(row) for row in rows],
        )
