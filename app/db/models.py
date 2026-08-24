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
from app.modules.compliance.models import ComplianceFramework, ComplianceFrameworkVersion, ComplianceControlDefinition, ProjectFrameworkAdoption, ProjectComplianceControl, ComplianceEvidence, ControlEvidenceLink, ComplianceScoreCalculation
from app.modules.sharing.models import InvestorShareGrant
from app.modules.investment.models import InvestmentOpportunity, InvestmentOpportunityVersion, InvestorProfile, InvestorThesisVersion
from app.modules.investment.matching_models import MatchingRun
from app.modules.investment.brief_models import InvestorOpportunityBriefRun, InvestorOpportunityBriefVersion
from app.modules.investment.brief_verification_models import BriefClaimVerification, BriefVerificationRun
from app.modules.events.models import EcosystemEvent, EventRegistration
from app.modules.network.models import ContactConsent, ContactPoint, ContactRequest

__all__ = ["AgentRun", "AssessmentInputSnapshot", "AuditLog", "BriefClaimVerification", "BriefVerificationRun", "ComplianceControlDefinition", "ComplianceEvidence", "ComplianceFramework", "ComplianceFrameworkVersion", "ComplianceScoreCalculation", "ContactConsent", "ContactPoint", "ContactRequest", "ControlEvidenceLink", "ContractAnalysis", "ContractFinding", "ConversationMessage", "ConversationThread", "Document", "DocumentProcessingJob", "DocumentVersion", "EcosystemEvent", "EventRegistration", "InvestmentOpportunity", "InvestmentOpportunityVersion", "InvestorProfile", "InvestorThesisVersion", "LaunchRoadmap", "LaunchRoadmapItem", "MatchingRun", "InvestorOpportunityBriefRun", "InvestorOpportunityBriefVersion", "Project", "ProjectComplianceControl", "ProjectFact", "ProjectFrameworkAdoption", "ProjectMember", "RegulatoryAssessment", "Role", "StartupProfile", "StartupProfileField", "StartupProfileRevision", "User", "UserIdentity", "UserRole", "InvestorShareGrant"]
