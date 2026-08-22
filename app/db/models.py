"""Import all migration-managed models into the single metadata registry."""

from app.modules.audit import AuditLog
from app.modules.identity.models import Role, User, UserIdentity, UserRole
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.projects.profile_models import StartupProfile, StartupProfileField, StartupProfileRevision
from app.modules.documents.models import Document, DocumentProcessingJob, DocumentVersion
from app.modules.documents.contract_analysis_models import ContractAnalysis, ContractFinding
from app.modules.ai.models import AgentRun, ConversationMessage, ConversationThread
from app.modules.regulatory.assessment_models import AssessmentInputSnapshot, RegulatoryAssessment
from app.modules.regulatory.roadmap_models import LaunchRoadmap, LaunchRoadmapItem

__all__ = ["AgentRun", "AssessmentInputSnapshot", "AuditLog", "ContractAnalysis", "ContractFinding", "ConversationMessage", "ConversationThread", "Document", "DocumentProcessingJob", "DocumentVersion", "LaunchRoadmap", "LaunchRoadmapItem", "Project", "ProjectFact", "ProjectMember", "RegulatoryAssessment", "Role", "StartupProfile", "StartupProfileField", "StartupProfileRevision", "User", "UserIdentity", "UserRole"]
