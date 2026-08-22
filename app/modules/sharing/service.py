from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.audit import AuditLog
from app.modules.compliance.models import ComplianceScoreCalculation
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import ProjectMember
from app.modules.projects.profile_models import StartupProfile, StartupProfileRevision
from app.modules.sharing.models import InvestorShareGrant
from app.modules.sharing.schemas import ShareGrantCreate, RevokeShareRequest

RESOURCE_TYPES = {"STARTUP_PROFILE_REVISION", "COMPLIANCE_SCORE_CALCULATION", "DOCUMENT_VERSION"}
MANAGERS = {"owner", "founder", "admin"}

class SharingService:
    def __init__(self, session: AsyncSession) -> None: self.session = session

    async def _manager(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> None:
        member = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
        if member is None or member.member_role not in MANAGERS:
            raise HTTPException(status_code=403, detail="Sharing permission denied")

    async def _resource(self, project_id: uuid.UUID, data: ShareGrantCreate) -> None:
        if data.resource_type not in RESOURCE_TYPES: raise HTTPException(status_code=400, detail="Resource type is not shareable")
        if await self.session.get(User, data.recipient_user_id) is None: raise HTTPException(status_code=404, detail="Recipient user not found")
        if data.resource_type == "STARTUP_PROFILE_REVISION":
            item = await self.session.scalar(select(StartupProfileRevision).join(StartupProfile, StartupProfile.id == StartupProfileRevision.profile_id).where(StartupProfileRevision.id == data.resource_id, StartupProfile.project_id == project_id))
            if item is None or data.resource_version_id is not None: raise HTTPException(status_code=404, detail="Profile revision not found")
        elif data.resource_type == "COMPLIANCE_SCORE_CALCULATION":
            item = await self.session.scalar(select(ComplianceScoreCalculation).where(ComplianceScoreCalculation.id == data.resource_id, ComplianceScoreCalculation.project_id == project_id))
            if item is None or data.resource_version_id is not None: raise HTTPException(status_code=404, detail="Compliance score not found")
        else:
            if data.resource_version_id is None: raise HTTPException(status_code=400, detail="Document grants require an exact version")
            item = await self.session.scalar(select(DocumentVersion).join(Document, Document.id == DocumentVersion.document_id).where(Document.id == data.resource_id, DocumentVersion.id == data.resource_version_id, Document.project_id == project_id, Document.deleted_at.is_(None)))
            if item is None: raise HTTPException(status_code=404, detail="Document version not found")

    async def create(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, data: ShareGrantCreate) -> InvestorShareGrant:
        await self._manager(actor, project_id)
        await self._resource(project_id, data)
        existing = await self.session.scalar(select(InvestorShareGrant).where(InvestorShareGrant.project_id == project_id, InvestorShareGrant.recipient_user_id == data.recipient_user_id, InvestorShareGrant.resource_type == data.resource_type, InvestorShareGrant.resource_id == data.resource_id, InvestorShareGrant.resource_version_id == data.resource_version_id, InvestorShareGrant.scope == data.scope, InvestorShareGrant.status == "ACTIVE"))
        if existing is not None: return existing
        grant = InvestorShareGrant(project_id=project_id, recipient_user_id=data.recipient_user_id, resource_type=data.resource_type, resource_id=data.resource_id, resource_version_id=data.resource_version_id, scope=data.scope, granted_by_user_id=actor.user_id)
        self.session.add(grant); await self.session.flush()
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="GRANT_CREATED", resource_type="investor_share_grant", resource_id=grant.id, project_id=project_id, metadata_json={"recipient_user_id": str(data.recipient_user_id), "shared_resource_type": data.resource_type, "shared_resource_id": str(data.resource_id), "shared_resource_version_id": str(data.resource_version_id) if data.resource_version_id else None, "scope": data.scope}))
        await self.session.commit()
        return grant

    async def list(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> list[InvestorShareGrant]:
        await self._manager(actor, project_id)
        return list((await self.session.scalars(select(InvestorShareGrant).where(InvestorShareGrant.project_id == project_id).order_by(InvestorShareGrant.granted_at, InvestorShareGrant.id))).all())

    async def revoke(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, grant_id: uuid.UUID, data: RevokeShareRequest) -> InvestorShareGrant:
        await self._manager(actor, project_id)
        grant = await self.session.scalar(select(InvestorShareGrant).where(InvestorShareGrant.id == grant_id, InvestorShareGrant.project_id == project_id))
        if grant is None: raise HTTPException(status_code=404, detail="Share grant not found")
        if grant.status == "ACTIVE":
            grant.status = "REVOKED"; grant.revoked_at = datetime.now(timezone.utc); grant.revoked_by_user_id = actor.user_id
            self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="GRANT_REVOKED", resource_type="investor_share_grant", resource_id=grant.id, project_id=project_id, metadata_json={"reason": data.reason}))
            await self.session.commit()
        return grant

    async def _payload(self, grant: InvestorShareGrant) -> dict:
        if grant.resource_type == "STARTUP_PROFILE_REVISION":
            revision = await self.session.scalar(select(StartupProfileRevision).join(StartupProfile, StartupProfile.id == StartupProfileRevision.profile_id).where(StartupProfileRevision.id == grant.resource_id, StartupProfile.project_id == grant.project_id))
            if revision is None: raise HTTPException(status_code=404, detail="Shared profile revision not found")
            return {"revision": revision.revision_number, "created_at": revision.created_at, "fields": [field for field in revision.snapshot if field.get("visibility") != "PRIVATE"]}
        if grant.resource_type == "COMPLIANCE_SCORE_CALCULATION":
            score = await self.session.scalar(select(ComplianceScoreCalculation).where(ComplianceScoreCalculation.id == grant.resource_id, ComplianceScoreCalculation.project_id == grant.project_id))
            if score is None: raise HTTPException(status_code=404, detail="Shared compliance score not found")
            explanation = score.explanation or {}
            return {"score": float(score.score) if score.score is not None else None, "evidence_coverage": float(score.evidence_coverage) if score.evidence_coverage is not None else None, "calculated_at": score.calculated_at, "method_key": score.method_key, "method_version": score.method_version, "evidence_policy_version": score.evidence_policy_version, "framework_version_id": score.framework_version_id, "limitations": explanation.get("limitations", [])}
        version = await self.session.scalar(select(DocumentVersion).join(Document, Document.id == DocumentVersion.document_id).where(DocumentVersion.id == grant.resource_version_id, Document.id == grant.resource_id, Document.project_id == grant.project_id, Document.deleted_at.is_(None)))
        if version is None: raise HTTPException(status_code=404, detail="Shared document version not found")
        return {"document_id": grant.resource_id, "document_version_id": version.id, "version_number": version.version_number, "original_filename": version.original_filename, "mime_type": version.mime_type, "size_bytes": version.size_bytes, "sha256": version.sha256}

    async def access(self, actor: AuthenticatedPrincipal, grant_id: uuid.UUID) -> tuple[InvestorShareGrant, dict]:
        grant = await self.session.scalar(select(InvestorShareGrant).where(InvestorShareGrant.id == grant_id, InvestorShareGrant.recipient_user_id == actor.user_id, InvestorShareGrant.status == "ACTIVE", InvestorShareGrant.scope == "READ"))
        if grant is None: raise HTTPException(status_code=404, detail="Shared resource not found")
        payload = await self._payload(grant)
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="SHARED_RESOURCE_ACCESSED", resource_type=grant.resource_type, resource_id=grant.resource_id, project_id=grant.project_id, metadata_json={"grant_id": str(grant.id), "resource_version_id": str(grant.resource_version_id) if grant.resource_version_id else None, "result": "allowed"}))
        await self.session.commit()
        return grant, payload
