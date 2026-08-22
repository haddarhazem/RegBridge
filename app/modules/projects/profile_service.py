import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import AuditLog
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.authorization import ProjectAuthorizationPolicy
from app.modules.projects.models import Project, ProjectMember
from app.modules.projects.profile_models import StartupProfile, StartupProfileField, StartupProfileRevision
from app.modules.projects.profile_schemas import ProfileVisibility, StartupProfilePatch


PROFILE_FIELD_SECTIONS = {
    "website": "identity",
    "fundraising_target": "funding",
    "investor_summary": "funding",
    "internal_notes": "operations",
    "employee_range": "team",
    "business_model": "business",
    "traction_summary": "business",
    "contact_email": "operations",
}


class StartupProfileService:
    def __init__(self, session: AsyncSession, policy: ProjectAuthorizationPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or ProjectAuthorizationPolicy()

    async def _project(self, project_id: uuid.UUID, *, lock: bool = False) -> Project:
        query = select(Project).where(Project.id == project_id)
        if lock:
            query = query.with_for_update()
        project = await self.session.scalar(query)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if project.project_type not in {"startup_in_creation", "existing_startup"}:
            raise HTTPException(status_code=404, detail="Startup profile not found")
        return project

    async def _membership(self, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
        return await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id, ProjectMember.status == "active"))

    async def _profile(self, project_id: uuid.UUID, *, lock: bool = False) -> StartupProfile | None:
        query = select(StartupProfile).where(StartupProfile.project_id == project_id)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def _internal_authorize(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, *, edit: bool = False, lock: bool = False) -> Project:
        project = await self._project(project_id, lock=lock)
        membership = await self._membership(project_id, actor.user_id)
        self.policy.require(self.policy.can_edit(membership) if edit else self.policy.can_view(project, membership))
        return project

    async def get_internal(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID):
        project = await self._internal_authorize(actor, project_id)
        profile = await self._profile(project.id)
        fields = [] if profile is None else list((await self.session.scalars(select(StartupProfileField).where(StartupProfileField.profile_id == profile.id).order_by(StartupProfileField.field_name))).all())
        return project, profile, fields

    async def get_public(self, project_id: uuid.UUID):
        project = await self._project(project_id)
        if project.visibility != "public":
            raise HTTPException(status_code=404, detail="Public startup profile not found")
        profile = await self._profile(project.id)
        if profile is None:
            return {}
        fields = await self.session.scalars(select(StartupProfileField).where(StartupProfileField.profile_id == profile.id, StartupProfileField.visibility == ProfileVisibility.PUBLIC.value).order_by(StartupProfileField.field_name))
        return {field.field_name: field.value for field in fields}

    async def update(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, data: StartupProfilePatch):
        async with self.session.begin():
            project = await self._internal_authorize(actor, project_id, edit=True, lock=True)
            profile = await self._profile(project.id, lock=True)
            if profile is None:
                profile = StartupProfile(project_id=project.id, current_revision=0)
                self.session.add(profile)
                await self.session.flush()
            existing = {field.field_name: field for field in (await self.session.scalars(select(StartupProfileField).where(StartupProfileField.profile_id == profile.id).with_for_update())).all()}
            changed_fields: list[str] = []
            visibility_changes: dict[str, list[str]] = {}
            for item in data.fields:
                field_name = item.field_name
                previous = existing.get(field_name)
                if previous is None:
                    previous_visibility = None
                    field = StartupProfileField(profile_id=profile.id, field_name=field_name, section=PROFILE_FIELD_SECTIONS[field_name], value=item.value, visibility=item.visibility.value)
                    self.session.add(field)
                    existing[field_name] = field
                else:
                    previous_visibility = previous.visibility
                    previous.value = item.value
                    previous.visibility = item.visibility.value
                changed_fields.append(field_name)
                if previous_visibility != item.visibility.value:
                    visibility_changes[field_name] = [previous_visibility, item.visibility.value]
            await self.session.flush()
            snapshot_fields = list((await self.session.scalars(select(StartupProfileField).where(StartupProfileField.profile_id == profile.id).order_by(StartupProfileField.field_name))).all())
            profile.current_revision += 1
            self.session.add(StartupProfileRevision(profile_id=profile.id, revision_number=profile.current_revision, snapshot=[{"field_name": field.field_name, "section": field.section, "value": field.value, "visibility": field.visibility} for field in snapshot_fields], changed_by_user_id=actor.user_id))
            self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="startup_profile.updated", resource_type="startup_profile", resource_id=profile.id, project_id=project.id, metadata_json={"fields": sorted(set(changed_fields)), "visibility_changes": visibility_changes, "revision": profile.current_revision}))
        return await self.get_internal(actor, project_id)

    async def history(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID):
        project = await self._internal_authorize(actor, project_id)
        profile = await self._profile(project.id)
        if profile is None:
            return []
        return list((await self.session.scalars(select(StartupProfileRevision).where(StartupProfileRevision.profile_id == profile.id).order_by(StartupProfileRevision.revision_number))).all())
