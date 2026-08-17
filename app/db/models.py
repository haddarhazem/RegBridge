"""Import all migration-managed models into the single metadata registry."""

from app.modules.audit import AuditLog
from app.modules.identity.models import Role, User, UserIdentity, UserRole
from app.modules.projects.models import Project, ProjectMember

__all__ = ["AuditLog", "Project", "ProjectMember", "Role", "User", "UserIdentity", "UserRole"]
