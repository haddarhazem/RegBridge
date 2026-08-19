"""Import all migration-managed models into the single metadata registry."""

from app.modules.audit import AuditLog
from app.modules.identity.models import Role, User, UserIdentity, UserRole
from app.modules.projects.models import Project, ProjectMember
from app.modules.documents.models import Document, DocumentProcessingJob, DocumentVersion
from app.modules.ai.models import AgentRun, ConversationMessage, ConversationThread

__all__ = ["AgentRun", "AuditLog", "ConversationMessage", "ConversationThread", "Document", "DocumentProcessingJob", "DocumentVersion", "Project", "ProjectMember", "Role", "User", "UserIdentity", "UserRole"]
