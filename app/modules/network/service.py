from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.models import InvestorProfile
from app.modules.network.models import ContactConsent, ContactPoint, ContactRequest
from app.modules.network.schemas import ContactAccept, ContactPointCreate, ContactRequestCreate, ContactDisclosure, ContactRequestResponse
from app.modules.projects.models import Project, ProjectMember

MANAGERS = {"owner", "founder", "admin"}

class ContactRequestService:
    def __init__(self, session: AsyncSession) -> None: self.session = session
    async def _recipient(self, request: ContactRequest) -> uuid.UUID:
        if request.target_type == "project":
            project = await self.session.get(Project, request.target_id)
            if project is None: raise HTTPException(status_code=404, detail="Contact target not found")
            return project.owner_user_id
        profile = await self.session.get(InvestorProfile, request.target_id)
        if profile is None: raise HTTPException(status_code=404, detail="Contact target not found")
        return profile.user_id
    async def _view(self, request: ContactRequest) -> ContactRequestResponse:
        return ContactRequestResponse(id=request.id, requester_user_id=request.requester_user_id, recipient_user_id=await self._recipient(request), source_project_id=request.source_project_id, target_type=request.target_type, target_id=request.target_id, message=request.message, status=request.status, responded_at=request.responded_at, created_at=request.created_at, updated_at=request.updated_at)
    async def _project_manager(self, actor, project_id):
        member = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
        if member is None or member.member_role not in MANAGERS: raise HTTPException(status_code=403, detail="Project authorization denied")
    async def _validate_target(self, actor, data):
        if data.target_type == "project":
            project = await self.session.get(Project, data.target_id)
            if project is None: raise HTTPException(status_code=404, detail="Project not found")
            if data.source_project_id is not None: raise HTTPException(status_code=422, detail="Project targets cannot have a source project")
            if project.owner_user_id == actor.user_id: raise HTTPException(status_code=400, detail="Self-contact is not allowed")
            if await self.session.scalar(select(InvestorProfile).where(InvestorProfile.user_id == actor.user_id)) is None: raise HTTPException(status_code=403, detail="Investor profile required")
            return project.owner_user_id
        profile = await self.session.get(InvestorProfile, data.target_id)
        if profile is None: raise HTTPException(status_code=404, detail="Investor profile not found")
        if data.source_project_id is None: raise HTTPException(status_code=422, detail="Startup requests require a source project")
        await self._project_manager(actor, data.source_project_id)
        if profile.user_id == actor.user_id: raise HTTPException(status_code=400, detail="Self-contact is not allowed")
        if await self.session.get(Project, data.source_project_id) is None: raise HTTPException(status_code=404, detail="Source project not found")
        return profile.user_id
    async def create_point(self, actor, data: ContactPointCreate) -> ContactPoint:
        if data.project_id is not None: await self._project_manager(actor, data.project_id)
        point = ContactPoint(owner_user_id=actor.user_id, project_id=data.project_id, channel=data.channel, value=data.value); self.session.add(point); await self.session.flush()
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="CONTACT_POINT_CREATED", resource_type="contact_point", resource_id=point.id, metadata_json={"channel":point.channel,"project_id":str(point.project_id) if point.project_id else None}))
        await self.session.commit(); return point
    async def points(self, actor): return list((await self.session.scalars(select(ContactPoint).where(ContactPoint.owner_user_id == actor.user_id, ContactPoint.active.is_(True)).order_by(ContactPoint.created_at, ContactPoint.id))).all())
    async def create(self, actor, data: ContactRequestCreate) -> ContactRequestResponse:
        recipient = await self._validate_target(actor, data)
        source_filter = ContactRequest.source_project_id.is_(None) if data.source_project_id is None else ContactRequest.source_project_id == data.source_project_id
        existing = await self.session.scalar(select(ContactRequest).where(ContactRequest.requester_user_id == actor.user_id, ContactRequest.target_type == data.target_type, ContactRequest.target_id == data.target_id, source_filter, ContactRequest.status == "pending"))
        if existing is not None: return await self._view(existing)
        request = ContactRequest(requester_user_id=actor.user_id, source_project_id=data.source_project_id, target_type=data.target_type, target_id=data.target_id, message=data.message); self.session.add(request)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.session.scalar(select(ContactRequest).where(ContactRequest.requester_user_id == actor.user_id, ContactRequest.target_type == data.target_type, ContactRequest.target_id == data.target_id, source_filter, ContactRequest.status == "pending"))
            if existing is not None:
                return await self._view(existing)
            raise
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="CONTACT_REQUEST_CREATED", resource_type="contact_request", resource_id=request.id, project_id=data.source_project_id, metadata_json={"recipient_user_id":str(recipient),"target_type":data.target_type,"target_id":str(data.target_id)}))
        await self.session.commit(); await self.session.refresh(request); return await self._view(request)
    async def _owned_recipient(self, actor, request_id, lock=True):
        query = select(ContactRequest).where(ContactRequest.id == request_id)
        if lock: query = query.with_for_update().execution_options(populate_existing=True)
        request = await self.session.scalar(query)
        if request is None: raise HTTPException(status_code=404, detail="Contact request not found")
        if await self._recipient(request) != actor.user_id: raise HTTPException(status_code=403, detail="Contact request recipient required")
        return request
    async def accept(self, actor, request_id, data: ContactAccept):
        request = await self._owned_recipient(actor, request_id)
        if request.status in {"declined", "cancelled"}: raise HTTPException(status_code=409, detail="Contact request is terminal")
        points = []
        if data.contact_point_ids:
            points = list((await self.session.scalars(select(ContactPoint).where(ContactPoint.id.in_(data.contact_point_ids), ContactPoint.owner_user_id == actor.user_id, ContactPoint.active.is_(True)))).all())
            if len(points) != len(set(data.contact_point_ids)): raise HTTPException(status_code=403, detail="Contact point access denied")
            for point in points:
                if request.target_type == "project" and point.project_id != request.target_id: raise HTTPException(status_code=403, detail="Contact point is outside the project")
                if request.target_type == "investor_profile" and point.project_id is not None: raise HTTPException(status_code=403, detail="Investor contact point cannot be project-scoped")
        if request.status == "pending": request.status = "accepted"; request.responded_at = datetime.now(timezone.utc); self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="CONTACT_REQUEST_ACCEPTED", resource_type="contact_request", resource_id=request.id, project_id=request.source_project_id, metadata_json={}))
        if data.contact_point_ids:
            for point in points:
                active = await self.session.scalar(select(ContactConsent).where(ContactConsent.request_id == request.id, ContactConsent.contact_point_id == point.id, ContactConsent.status == "active"))
                if active is None:
                    consent = ContactConsent(request_id=request.id, contact_point_id=point.id, granted_by_user_id=actor.user_id, channel=point.channel, value_snapshot=point.value, status="active"); self.session.add(consent); await self.session.flush()
                    self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="CONTACT_CONSENT_GRANTED", resource_type="contact_consent", resource_id=consent.id, project_id=request.source_project_id, metadata_json={"request_id":str(request.id),"contact_point_id":str(point.id),"channel":point.channel}))
        await self.session.commit(); await self.session.refresh(request); return await self._view(request)
    async def refuse(self, actor, request_id):
        request = await self._owned_recipient(actor, request_id)
        if request.status == "accepted": raise HTTPException(status_code=409, detail="Accepted request cannot be refused")
        if request.status == "pending": request.status = "declined"; request.responded_at = datetime.now(timezone.utc); self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="CONTACT_REQUEST_REFUSED", resource_type="contact_request", resource_id=request.id, project_id=request.source_project_id, metadata_json={})) ; await self.session.commit()
        await self.session.refresh(request); return await self._view(request)
    async def revoke(self, actor, consent_id):
        consent = await self.session.scalar(select(ContactConsent).where(ContactConsent.id == consent_id).with_for_update())
        if consent is None: raise HTTPException(status_code=404, detail="Consent not found")
        request = await self.session.get(ContactRequest, consent.request_id)
        if request is None or await self._recipient(request) != actor.user_id: raise HTTPException(status_code=403, detail="Consent owner required")
        if consent.status == "active": consent.status = "revoked"; consent.revoked_at = datetime.now(timezone.utc); self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="CONTACT_CONSENT_REVOKED", resource_type="contact_consent", resource_id=consent.id, project_id=request.source_project_id, metadata_json={"request_id":str(request.id),"channel":consent.channel})); await self.session.commit()
        return consent
    async def disclose(self, actor, request_id):
        request = await self.session.scalar(select(ContactRequest).where(ContactRequest.id == request_id, ContactRequest.requester_user_id == actor.user_id))
        if request is None or request.status != "accepted": raise HTTPException(status_code=404, detail="Contact disclosure not available")
        consents = list((await self.session.scalars(select(ContactConsent).where(ContactConsent.request_id == request.id, ContactConsent.status == "active"))).all())
        return ContactDisclosure(request_id=request.id, contacts=[{"channel":item.channel,"value":item.value_snapshot} for item in consents])
    async def list(self, actor, limit: int = 50, offset: int = 0):
        project_ids = select(Project.id).where(Project.owner_user_id == actor.user_id)
        investor_ids = select(InvestorProfile.id).where(InvestorProfile.user_id == actor.user_id)
        query = select(ContactRequest).where(or_(ContactRequest.requester_user_id == actor.user_id, and_(ContactRequest.target_type == "project", ContactRequest.target_id.in_(project_ids)), and_(ContactRequest.target_type == "investor_profile", ContactRequest.target_id.in_(investor_ids)))).order_by(ContactRequest.created_at.desc(), ContactRequest.id).offset(offset).limit(limit)
        requests = list((await self.session.scalars(query)).all())
        project_target_ids = {item.target_id for item in requests if item.target_type == "project"}
        investor_target_ids = {item.target_id for item in requests if item.target_type == "investor_profile"}
        project_owners = {}
        if project_target_ids:
            project_owners = dict((await self.session.execute(select(Project.id, Project.owner_user_id).where(Project.id.in_(project_target_ids)))).all())
        investor_owners = {}
        if investor_target_ids:
            investor_owners = dict((await self.session.execute(select(InvestorProfile.id, InvestorProfile.user_id).where(InvestorProfile.id.in_(investor_target_ids)))).all())
        return [ContactRequestResponse(id=item.id, requester_user_id=item.requester_user_id, recipient_user_id=project_owners[item.target_id] if item.target_type == "project" else investor_owners[item.target_id], source_project_id=item.source_project_id, target_type=item.target_type, target_id=item.target_id, message=item.message, status=item.status, responded_at=item.responded_at, created_at=item.created_at, updated_at=item.updated_at) for item in requests]
