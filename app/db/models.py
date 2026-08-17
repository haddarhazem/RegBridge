"""Import all migration-managed models into the single metadata registry."""

from app.modules.audit import AuditLog
from app.modules.identity.models import Role, User, UserIdentity, UserRole
from app.modules.projects.models import Project, ProjectMember
from app.modules.documents.models import Document, DocumentProcessingJob, DocumentVersion

__all__ = ["AuditLog", "Document", "DocumentProcessingJob", "DocumentVersion", "Project", "ProjectMember", "Role", "User", "UserIdentity", "UserRole"]
