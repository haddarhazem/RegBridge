"""Import all migration-managed models into the single metadata registry."""

from app.modules.audit import AuditLog
from app.modules.identity.models import Role, User, UserIdentity, UserRole
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.documents.models import Document, DocumentProcessingJob, DocumentVersion
from app.modules.ai.models import AgentRun, ConversationMessage, ConversationThread
from app.modules.regulatory.assessment_models import AssessmentInputSnapshot, RegulatoryAssessment
from app.modules.regulatory.roadmap_models import LaunchRoadmap, LaunchRoadmapItem

__all__ = ["AgentRun", "AssessmentInputSnapshot", "AuditLog", "ConversationMessage", "ConversationThread", "Document", "DocumentProcessingJob", "DocumentVersion", "LaunchRoadmap", "LaunchRoadmapItem", "Project", "ProjectFact", "ProjectMember", "RegulatoryAssessment", "Role", "User", "UserIdentity", "UserRole"]
