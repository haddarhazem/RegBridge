from dataclasses import dataclass

from fastapi import HTTPException, status

from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember


@dataclass(frozen=True)
class ProjectAuthorizationPolicy:
    """Project-scoped authorization rules; absent or inactive membership denies access."""

    def can_view(self, project: Project, membership: ProjectMember | None) -> bool:
        if membership is not None and membership.status == "active":
            return True
        return project.visibility in {"authenticated", "public"}

    def can_edit(self, membership: ProjectMember | None) -> bool:
        return membership is not None and membership.status == "active" and membership.member_role in {"owner", "founder", "admin"}

    def can_manage_members(self, membership: ProjectMember | None) -> bool:
        return membership is not None and membership.status == "active" and membership.member_role in {"owner", "founder", "admin"}

    def can_manage_target(self, manager: ProjectMember, target: ProjectMember | None) -> bool:
        if manager.status != "active" or manager.member_role not in {"owner", "founder", "admin"}:
            return False
        if target is not None and target.member_role == "owner":
            return manager.member_role == "owner" and False
        return True

    def require_authenticated(self, principal: AuthenticatedPrincipal | None) -> AuthenticatedPrincipal:
        if principal is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        return principal

    def require(self, allowed: bool) -> None:
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied")
