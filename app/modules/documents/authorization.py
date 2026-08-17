from app.modules.projects.models import ProjectMember


class DocumentAuthorizationPolicy:
    """Document access policy layered on SCRUM-179 active project membership."""

    def can_upload(self, membership: ProjectMember | None) -> bool:
        return membership is not None and membership.status == "active" and membership.member_role in {"owner", "founder", "admin", "member"}

    def can_manage(self, membership: ProjectMember | None, owner_user_id, actor_user_id) -> bool:
        return actor_user_id == owner_user_id or membership is not None and membership.status == "active" and membership.member_role in {"owner", "founder", "admin"}

    def can_read(self, visibility: str, classification: str, membership: ProjectMember | None, owner_user_id, actor_user_id) -> bool:
        if actor_user_id == owner_user_id:
            return True
        if membership is None or membership.status != "active":
            return False
        if classification == "highly_confidential" and membership.member_role not in {"owner", "founder", "admin"}:
            return False
        if visibility == "project_members":
            return True
        if visibility == "public":
            return True
        # private is restricted to the owner and project managers; shared is fail-closed.
        return visibility == "private" and membership.member_role in {"owner", "founder", "admin"}
