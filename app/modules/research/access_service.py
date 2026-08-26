from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import AuditLog
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import ProjectMember
from app.modules.research.models import ResearchAccessRequest, ResearchDiscovery, ResearchDiscoveryVersion, ResearchOutput, ResearchOutputVersion, ResearcherProfile
from app.modules.sharing.models import InvestorShareGrant

SCOPES = {"CONTACT", "DISCOVERY_READ", "FULL_DOCUMENT_READ", "COLLABORATION"}
TERMINAL = {"REFUSED", "REVOKED"}


class ResearchAccessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _output(self, output_id: uuid.UUID) -> ResearchOutput:
        output = await self.session.get(ResearchOutput, output_id)
        if output is None:
            raise HTTPException(404, "Research output not found")
        return output

    async def _owner(self, actor: AuthenticatedPrincipal, output_id: uuid.UUID) -> None:
        owner = await self.session.scalar(select(ResearchOutput).join(ResearcherProfile).where(ResearchOutput.id == output_id, ResearcherProfile.user_id == actor.user_id))
        if owner is None:
            raise HTTPException(403, "Research access management denied")

    async def _target(self, output_id: uuid.UUID, output_version_id: uuid.UUID | None, discovery_version_id: uuid.UUID | None) -> None:
        if output_version_id is None and discovery_version_id is None:
            raise HTTPException(422, "At least one exact research version target is required")
        if output_version_id is not None:
            version = await self.session.scalar(select(ResearchOutputVersion).where(ResearchOutputVersion.id == output_version_id, ResearchOutputVersion.research_output_id == output_id))
            if version is None:
                raise HTTPException(404, "Research output version not found")
        if discovery_version_id is not None:
            version = await self.session.scalar(select(ResearchDiscoveryVersion).join(ResearchDiscovery, ResearchDiscovery.id == ResearchDiscoveryVersion.discovery_id).where(ResearchDiscoveryVersion.id == discovery_version_id, ResearchDiscovery.research_output_id == output_id))
            if version is None:
                raise HTTPException(404, "Research discovery version not found")

    async def _request(self, actor: AuthenticatedPrincipal, request_id: uuid.UUID, *, owner: bool = False) -> ResearchAccessRequest:
        query = select(ResearchAccessRequest).where(ResearchAccessRequest.id == request_id)
        request = await self.session.scalar(query)
        if request is None:
            raise HTTPException(404, "Research access request not found")
        if owner:
            await self._owner(actor, request.research_output_id)
        elif request.requester_user_id != actor.user_id:
            raise HTTPException(404, "Research access request not found")
        return request

    async def create(self, actor: AuthenticatedPrincipal, data) -> ResearchAccessRequest:
        await self._output(data.research_output_id)
        await self._target(data.research_output_id, data.research_output_version_id, data.research_discovery_version_id)
        scopes = list(dict.fromkeys(data.requested_scopes))
        if not set(scopes) <= SCOPES:
            raise HTTPException(422, "Invalid research access scope")
        if "FULL_DOCUMENT_READ" in scopes and data.research_output_version_id is None:
            raise HTTPException(422, "Full document access requires an exact output version")
        if "DISCOVERY_READ" in scopes and data.research_discovery_version_id is None:
            raise HTTPException(422, "Discovery access requires an exact discovery version")
        if data.requester_project_id is not None:
            member = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == data.requester_project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
            if member is None:
                raise HTTPException(403, "Requester project access denied")
        request = ResearchAccessRequest(research_output_id=data.research_output_id, research_output_version_id=data.research_output_version_id, research_discovery_version_id=data.research_discovery_version_id, requester_user_id=actor.user_id, requester_project_id=data.requester_project_id, requested_scopes=scopes, message=data.message)
        self.session.add(request)
        await self.session.flush()
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="RESEARCH_ACCESS_REQUEST_CREATED", resource_type="research_access_request", resource_id=request.id, project_id=data.requester_project_id, metadata_json={"requested_scopes": scopes, "research_output_id": str(data.research_output_id), "research_output_version_id": str(data.research_output_version_id) if data.research_output_version_id else None, "research_discovery_version_id": str(data.research_discovery_version_id) if data.research_discovery_version_id else None}))
        await self.session.commit()
        return request

    async def get(self, actor: AuthenticatedPrincipal, request_id: uuid.UUID) -> ResearchAccessRequest:
        request = await self.session.scalar(select(ResearchAccessRequest).where(ResearchAccessRequest.id == request_id))
        if request is None:
            raise HTTPException(404, "Research access request not found")
        if request.requester_user_id != actor.user_id:
            try:
                await self._owner(actor, request.research_output_id)
            except HTTPException:
                raise HTTPException(404, "Research access request not found") from None
        return request

    async def decide(self, actor: AuthenticatedPrincipal, request_id: uuid.UUID, action: str, data) -> ResearchAccessRequest:
        request = await self._request(actor, request_id, owner=True)
        if request.status != "PENDING":
            raise HTTPException(409, "Research access request transition is not allowed")
        requested = set(request.requested_scopes)
        if action == "ACCEPTED":
            granted = list(request.requested_scopes)
        elif action == "LIMITED":
            granted = list(dict.fromkeys(data.granted_scopes or []))
            if not granted or not set(granted) < requested:
                raise HTTPException(422, "Limited scopes must be a non-empty strict subset")
        elif action == "REFUSED":
            granted = []
        else:
            raise HTTPException(400, "Unsupported research access decision")
        if request.requester_project_id is None and granted:
            raise HTTPException(422, "A requester project is required for granted access")
        request.status = action
        request.granted_scopes = granted
        request.decided_by_user_id = actor.user_id
        request.decided_at = datetime.now(timezone.utc)
        if granted:
            for scope in granted:
                discovery_scope = scope == "DISCOVERY_READ"
                resource_type = "RESEARCH_DISCOVERY_VERSION" if discovery_scope else "RESEARCH_OUTPUT_VERSION"
                resource_id = request.research_discovery_version_id if discovery_scope else request.research_output_id
                resource_version_id = request.research_discovery_version_id if discovery_scope else request.research_output_version_id
                self.session.add(InvestorShareGrant(project_id=request.requester_project_id, recipient_user_id=request.requester_user_id, resource_type=resource_type, resource_id=resource_id, resource_version_id=resource_version_id, scope=scope, granted_by_user_id=actor.user_id, request_id=request.id))
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action=f"RESEARCH_ACCESS_REQUEST_{action}", resource_type="research_access_request", resource_id=request.id, project_id=request.requester_project_id, metadata_json={"granted_scopes": granted}))
        await self.session.commit()
        return request

    async def revoke(self, actor: AuthenticatedPrincipal, request_id: uuid.UUID) -> ResearchAccessRequest:
        request = await self._request(actor, request_id, owner=True)
        if request.status not in {"ACCEPTED", "LIMITED"}:
            raise HTTPException(409, "Only active research access can be revoked")
        request.status = "REVOKED"
        request.revoked_at = datetime.now(timezone.utc)
        grants = (await self.session.scalars(select(InvestorShareGrant).where(InvestorShareGrant.request_id == request.id, InvestorShareGrant.status == "ACTIVE"))).all()
        for grant in grants:
            grant.status = "REVOKED"
            grant.revoked_by_user_id = actor.user_id
            grant.revoked_at = request.revoked_at
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="RESEARCH_ACCESS_REQUEST_REVOKED", resource_type="research_access_request", resource_id=request.id, project_id=request.requester_project_id, metadata_json={"revoked_grant_count": len(grants)}))
        await self.session.commit()
        return request

    async def has_scope(self, actor: AuthenticatedPrincipal, *, output_id: uuid.UUID | None = None, output_version_id: uuid.UUID | None = None, discovery_version_id: uuid.UUID | None = None, scope: str) -> bool:
        resource_type = "RESEARCH_DISCOVERY_VERSION" if discovery_version_id else "RESEARCH_OUTPUT_VERSION"
        resource_id = discovery_version_id or output_id
        if resource_id is None:
            return False
        grant = await self.session.scalar(select(InvestorShareGrant).where(InvestorShareGrant.recipient_user_id == actor.user_id, InvestorShareGrant.resource_type == resource_type, InvestorShareGrant.resource_id == resource_id, InvestorShareGrant.resource_version_id == (discovery_version_id or output_version_id), InvestorShareGrant.scope == scope, InvestorShareGrant.status == "ACTIVE"))
        if grant is None:
            return False
        return await self.session.scalar(select(ProjectMember.project_id).where(ProjectMember.project_id == grant.project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active")) is not None
