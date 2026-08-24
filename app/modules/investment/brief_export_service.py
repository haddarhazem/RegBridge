from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.brief_export import RENDERER_VERSION, render_opportunity_brief_pdf
from app.modules.investment.brief_models import InvestorOpportunityBriefRun, InvestorOpportunityBriefVersion
from app.modules.investment.brief_service import OpportunityBriefService
from app.modules.investment.brief_schemas import BriefVersionResponse, OpportunityBriefContent
from app.modules.investment.brief_verification_models import BriefVerificationRun
from app.modules.sharing.models import InvestorShareGrant


RESOURCE_TYPE = "INVESTOR_OPPORTUNITY_BRIEF_VERSION"


class BriefExportShareService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _owner_version(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID, version_id: uuid.UUID) -> tuple[InvestorOpportunityBriefRun, InvestorOpportunityBriefVersion]:
        row = await self.session.execute(
            select(InvestorOpportunityBriefRun, InvestorOpportunityBriefVersion)
            .join(InvestorOpportunityBriefVersion, InvestorOpportunityBriefVersion.brief_run_id == InvestorOpportunityBriefRun.id)
            .where(
                InvestorOpportunityBriefRun.id == run_id,
                InvestorOpportunityBriefRun.investor_user_id == actor.user_id,
                InvestorOpportunityBriefVersion.id == version_id,
            )
        )
        result = row.first()
        if result is None:
            raise HTTPException(status_code=404, detail="Opportunity brief version not found")
        return result

    async def _eligible(self, run: InvestorOpportunityBriefRun, version: InvestorOpportunityBriefVersion) -> BriefVerificationRun:
        if version.status != "APPROVED":
            raise HTTPException(status_code=409, detail="Only approved brief versions can be exported or shared")
        if (
            version.brief_run_id != run.id
            or version.investor_thesis_version_id != run.investor_thesis_version_id
            or version.startup_snapshot_revision_id != run.startup_snapshot_revision_id
            or version.matching_run_id != run.matching_run_id
        ):
            raise HTTPException(status_code=409, detail="Brief source references are inconsistent")
        verification = await self.session.scalar(
            select(BriefVerificationRun)
            .where(
                BriefVerificationRun.brief_run_id == run.id,
                BriefVerificationRun.brief_version_id == version.id,
                BriefVerificationRun.status == "VERIFIED",
            )
            .order_by(BriefVerificationRun.created_at.desc(), BriefVerificationRun.id.desc())
            .limit(1)
        )
        if verification is None:
            raise HTTPException(status_code=409, detail="Exact verified version is required")
        return verification

    async def _safe_response(self, version: InvestorOpportunityBriefVersion) -> BriefVersionResponse:
        return await OpportunityBriefService(self.session).version_response(version)

    async def export_owner(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID, version_id: uuid.UUID) -> tuple[bytes, int, str]:
        run, version = await self._owner_version(actor, run_id, version_id)
        await self._eligible(run, version)
        content = OpportunityBriefContent.model_validate({key: version.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")})
        pdf = render_opportunity_brief_pdf(content.model_dump(mode="json"), version.version_number)
        digest = hashlib.sha256(pdf).hexdigest()
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="EXPORT", resource_type=RESOURCE_TYPE, resource_id=version.id, project_id=run.startup_project_id, metadata_json={"brief_run_id": str(run.id), "version_id": str(version.id), "format": "PDF", "sha256": digest, "renderer_version": RENDERER_VERSION}))
        await self.session.commit()
        return pdf, version.version_number, digest

    async def create_share(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID, version_id: uuid.UUID, recipient_user_id: uuid.UUID) -> InvestorShareGrant:
        run, version = await self._owner_version(actor, run_id, version_id)
        await self._eligible(run, version)
        if await self.session.get(User, recipient_user_id) is None:
            raise HTTPException(status_code=404, detail="Recipient user not found")
        existing = await self.session.scalar(
            select(InvestorShareGrant).where(
                InvestorShareGrant.project_id == run.startup_project_id,
                InvestorShareGrant.recipient_user_id == recipient_user_id,
                InvestorShareGrant.resource_type == RESOURCE_TYPE,
                InvestorShareGrant.resource_id == version.id,
                InvestorShareGrant.resource_version_id.is_(None),
                InvestorShareGrant.scope == "READ",
                InvestorShareGrant.status == "ACTIVE",
            )
        )
        if existing is not None:
            return existing
        grant = InvestorShareGrant(project_id=run.startup_project_id, recipient_user_id=recipient_user_id, resource_type=RESOURCE_TYPE, resource_id=version.id, scope="READ", granted_by_user_id=actor.user_id)
        self.session.add(grant)
        await self.session.flush()
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="SHARE_CREATED", resource_type=RESOURCE_TYPE, resource_id=version.id, project_id=run.startup_project_id, metadata_json={"grant_id": str(grant.id), "recipient_user_id": str(recipient_user_id), "scope": "READ"}))
        await self.session.commit()
        await self.session.refresh(grant)
        return grant

    async def shared_version(self, actor: AuthenticatedPrincipal, version_id: uuid.UUID) -> tuple[InvestorShareGrant, InvestorOpportunityBriefRun, InvestorOpportunityBriefVersion]:
        grant = await self.session.scalar(select(InvestorShareGrant).where(InvestorShareGrant.recipient_user_id == actor.user_id, InvestorShareGrant.resource_type == RESOURCE_TYPE, InvestorShareGrant.resource_id == version_id, InvestorShareGrant.scope == "READ", InvestorShareGrant.status == "ACTIVE"))
        if grant is None:
            raise HTTPException(status_code=404, detail="Shared brief not found")
        # Resolve the exact immutable version through the active grant.
        version = await self.session.get(InvestorOpportunityBriefVersion, version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="Shared brief not found")
        run = await self.session.get(InvestorOpportunityBriefRun, version.brief_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Shared brief not found")
        await self._eligible(run, version)
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="SHARE_ACCESSED", resource_type=RESOURCE_TYPE, resource_id=version.id, project_id=run.startup_project_id, metadata_json={"grant_id": str(grant.id)}))
        await self.session.commit()
        return grant, run, version

    async def list_shared(self, actor: AuthenticatedPrincipal) -> list[tuple[InvestorShareGrant, BriefVersionResponse]]:
        grants = list((await self.session.scalars(select(InvestorShareGrant).where(InvestorShareGrant.recipient_user_id == actor.user_id, InvestorShareGrant.resource_type == RESOURCE_TYPE, InvestorShareGrant.scope == "READ", InvestorShareGrant.status == "ACTIVE").order_by(InvestorShareGrant.granted_at, InvestorShareGrant.id))).all())
        result: list[tuple[InvestorShareGrant, BriefVersionResponse]] = []
        for grant in grants:
            version = await self.session.get(InvestorOpportunityBriefVersion, grant.resource_id)
            if version is None:
                continue
            run = await self.session.get(InvestorOpportunityBriefRun, version.brief_run_id)
            if run is None:
                continue
            try:
                await self._eligible(run, version)
            except HTTPException:
                continue
            result.append((grant, await self._safe_response(version)))
        return result

    async def export_shared(self, actor: AuthenticatedPrincipal, version_id: uuid.UUID) -> tuple[bytes, int, str]:
        _, run, version = await self.shared_version(actor, version_id)
        content = OpportunityBriefContent.model_validate({key: version.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")})
        pdf = render_opportunity_brief_pdf(content.model_dump(mode="json"), version.version_number)
        digest = hashlib.sha256(pdf).hexdigest()
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="EXPORT", resource_type=RESOURCE_TYPE, resource_id=version.id, project_id=run.startup_project_id, metadata_json={"brief_run_id": str(run.id), "version_id": str(version.id), "format": "PDF", "sha256": digest, "renderer_version": RENDERER_VERSION, "shared": True}))
        await self.session.commit()
        return pdf, version.version_number, digest

    async def revoke_share(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID, version_id: uuid.UUID, grant_id: uuid.UUID) -> InvestorShareGrant:
        run, version = await self._owner_version(actor, run_id, version_id)
        grant = await self.session.scalar(select(InvestorShareGrant).where(InvestorShareGrant.id == grant_id, InvestorShareGrant.project_id == run.startup_project_id, InvestorShareGrant.resource_type == RESOURCE_TYPE, InvestorShareGrant.resource_id == version.id))
        if grant is None:
            raise HTTPException(status_code=404, detail="Share grant not found")
        if grant.status == "ACTIVE":
            grant.status = "REVOKED"
            grant.revoked_by_user_id = actor.user_id
            grant.revoked_at = datetime.now(timezone.utc)
            self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="SHARE_REVOKED", resource_type=RESOURCE_TYPE, resource_id=version.id, project_id=run.startup_project_id, metadata_json={"grant_id": str(grant.id)}))
            await self.session.commit()
        return grant
