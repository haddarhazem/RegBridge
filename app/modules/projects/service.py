import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.audit import AuditLog
from app.modules.projects.authorization import ProjectAuthorizationPolicy
from app.modules.projects.models import Project, ProjectMember
from app.modules.projects.onboarding import onboarding_status
from app.modules.projects.schemas import IdeaOnboardingUpdate, IdeaProjectCreate, ProjectCreate, ProjectMemberInvite, ProjectMemberUpdate, ProjectUpdate


class ProjectService:
    def __init__(self, session: AsyncSession, policy: ProjectAuthorizationPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or ProjectAuthorizationPolicy()

    async def _project(self, project_id: uuid.UUID) -> Project:
        project = await self.session.scalar(select(Project).where(Project.id == project_id))
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    async def _membership(self, project_id: uuid.UUID, user_id: uuid.UUID, *, active_only: bool = False) -> ProjectMember | None:
        query = select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        if active_only:
            query = query.where(ProjectMember.status == "active")
        return await self.session.scalar(query)

    async def _audit(self, actor: AuthenticatedPrincipal, action: str, project_id: uuid.UUID, resource_id: uuid.UUID, resource_type: str, metadata: dict) -> None:
        self.session.add(
            AuditLog(
                actor_user_id=actor.user_id,
                actor_type="user",
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                project_id=project_id,
                metadata_json=metadata,
            )
        )

    async def create(self, actor: AuthenticatedPrincipal, data: ProjectCreate) -> Project:
        async with self.session.begin():
            project = Project(owner_user_id=actor.user_id, **data.model_dump())
            self.session.add(project)
            await self.session.flush()
            self.session.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=actor.user_id,
                    member_role="owner",
                    status="active",
                    joined_at=datetime.now(timezone.utc),
                )
            )
            await self._audit(actor, "project.created", project.id, project.id, "project", {})
        return project

    async def create_idea(self, actor: AuthenticatedPrincipal, data: IdeaProjectCreate) -> Project:
        async with self.session.begin():
            project = Project(
                owner_user_id=actor.user_id,
                project_type="idea",
                display_name=data.display_name,
                raw_description=data.display_name or "Idea project",
                target_market=None,
                confirmed_fields={},
                onboarding_status="in_progress",
            )
            self.session.add(project)
            await self.session.flush()
            self.session.add(ProjectMember(
                project_id=project.id,
                user_id=actor.user_id,
                member_role="owner",
                status="active",
                joined_at=datetime.now(timezone.utc),
            ))
            await self._audit(actor, "project.idea_created", project.id, project.id, "project", {})
        return project

    async def get_idea_for_user(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> Project:
        project, _ = await self.get_for_user(actor, project_id)
        if project.project_type != "idea":
            raise HTTPException(status_code=404, detail="Idea project not found")
        return project

    async def update_onboarding(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, data: IdeaOnboardingUpdate) -> Project:
        async with self.session.begin():
            project = await self._project(project_id)
            if project.project_type != "idea":
                raise HTTPException(status_code=404, detail="Idea project not found")
            membership = await self._membership(project_id, actor.user_id, active_only=True)
            self.policy.require(self.policy.can_edit(membership))
            changes = data.model_dump(exclude_unset=True, exclude={"confirm"})
            if "data" in changes:
                changes["data_context"] = changes.pop("data")
            for field, value in changes.items():
                setattr(project, field, value)
            confirmed = dict(project.confirmed_fields or {})
            for field in data.confirm:
                confirmed[field] = "confirmed"
            project.confirmed_fields = confirmed
            project.onboarding_status = onboarding_status(project)
            await self._audit(actor, "project.onboarding_updated", project.id, project.id, "project", {"fields": sorted(changes), "confirmed": sorted(data.confirm)})
        return project

    async def get_for_user(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> tuple[Project, ProjectMember | None]:
        project = await self._project(project_id)
        membership = await self._membership(project_id, actor.user_id, active_only=True)
        if not self.policy.can_view(project, membership):
            raise HTTPException(status_code=404, detail="Project not found")
        return project, membership

    async def update(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, data: ProjectUpdate) -> Project:
        async with self.session.begin():
            project = await self._project(project_id)
            membership = await self._membership(project_id, actor.user_id, active_only=True)
            self.policy.require(self.policy.can_edit(membership))
            changes = data.model_dump(exclude_unset=True)
            for field, value in changes.items():
                setattr(project, field, value)
            await self._audit(actor, "project.updated", project.id, project.id, "project", {"fields": sorted(changes)})
        return project

    async def list_members(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> list[ProjectMember]:
        project = await self._project(project_id)
        membership = await self._membership(project_id, actor.user_id, active_only=True)
        self.policy.require(membership is not None and self.policy.can_view(project, membership))
        return list((await self.session.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id).order_by(ProjectMember.created_at))).all())

    async def invite(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, data: ProjectMemberInvite) -> ProjectMember:
        async with self.session.begin():
            project = await self._project(project_id)
            manager = await self._membership(project_id, actor.user_id, active_only=True)
            self.policy.require(self.policy.can_manage_members(manager))
            user = await self.session.scalar(select(User).where(User.id == data.user_id))
            if user is None or user.status != "active":
                raise HTTPException(status_code=404, detail="User not found")
            target = await self._membership(project_id, data.user_id)
            if target is not None and target.status == "active":
                raise HTTPException(status_code=409, detail="User is already a project member")
            if target is None:
                target = ProjectMember(project_id=project_id, user_id=data.user_id, member_role=data.member_role, status="invited")
                self.session.add(target)
            else:
                target.member_role = data.member_role
                target.status = "invited"
                target.invited_by_user_id = actor.user_id
                target.joined_at = None
            target.invited_by_user_id = actor.user_id
            await self._audit(actor, "project.member.invited", project.id, data.user_id, "project_member", {"member_role": data.member_role, "target_user_id": str(data.user_id)})
        return target

    async def accept(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> ProjectMember:
        async with self.session.begin():
            project = await self._project(project_id)
            target = await self._membership(project_id, actor.user_id)
            if target is None or target.status != "invited":
                raise HTTPException(status_code=404, detail="Invitation not found")
            target.status = "active"
            target.joined_at = datetime.now(timezone.utc)
            await self._audit(actor, "project.member.accepted", project.id, actor.user_id, "project_member", {})
        return target

    async def revoke(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember:
        async with self.session.begin():
            project = await self._project(project_id)
            manager = await self._membership(project_id, actor.user_id, active_only=True)
            target = await self._membership(project_id, user_id)
            self.policy.require(target is not None and manager is not None and self.policy.can_manage_target(manager, target))
            if target.member_role == "owner":
                raise HTTPException(status_code=409, detail="The owner membership cannot be revoked")
            target.status = "revoked"
            await self._audit(actor, "project.member.revoked", project.id, user_id, "project_member", {"target_user_id": str(user_id)})
        return target

    async def change_role(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, user_id: uuid.UUID, data: ProjectMemberUpdate) -> ProjectMember:
        async with self.session.begin():
            project = await self._project(project_id)
            manager = await self._membership(project_id, actor.user_id, active_only=True)
            target = await self._membership(project_id, user_id)
            self.policy.require(target is not None and target.status == "active" and manager is not None and self.policy.can_manage_target(manager, target))
            if target.member_role == "owner":
                raise HTTPException(status_code=409, detail="The owner role cannot be changed")
            old_role = target.member_role
            target.member_role = data.member_role
            await self._audit(actor, "project.member.role_changed", project.id, user_id, "project_member", {"old_role": old_role, "new_role": data.member_role, "target_user_id": str(user_id)})
        return target
