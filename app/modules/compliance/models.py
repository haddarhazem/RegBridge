import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ComplianceFramework(Base):
    __tablename__ = "compliance_frameworks"
    __table_args__ = (UniqueConstraint("stable_key", name="uq_compliance_frameworks_stable_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    stable_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ComplianceFrameworkVersion(Base):
    __tablename__ = "compliance_framework_versions"
    __table_args__ = (
        UniqueConstraint("framework_id", "version_identifier", name="uq_compliance_framework_versions_identifier"),
        CheckConstraint("status IN ('draft', 'active', 'retired')", name="compliance_framework_versions_status"),
        Index("ix_compliance_framework_versions_framework_status", "framework_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    framework_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_frameworks.id", ondelete="RESTRICT"), nullable=False)
    version_identifier: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ComplianceControlDefinition(Base):
    __tablename__ = "compliance_control_definitions"
    __table_args__ = (
        UniqueConstraint("framework_version_id", "stable_key", name="uq_compliance_control_definitions_version_key"),
        Index("ix_compliance_control_definitions_version_order", "framework_version_id", "display_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    framework_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_framework_versions.id", ondelete="RESTRICT"), nullable=False)
    stable_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120))
    source_references: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class ProjectFrameworkAdoption(Base):
    __tablename__ = "project_framework_adoptions"
    __table_args__ = (
        UniqueConstraint("project_id", "framework_version_id", name="uq_project_framework_adoptions_version"),
        CheckConstraint("status IN ('active', 'superseded')", name="project_framework_adoptions_status"),
        Index("ix_project_framework_adoptions_project_status", "project_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    framework_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_framework_versions.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    adopted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    adopted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectComplianceControl(Base):
    __tablename__ = "project_compliance_controls"
    __table_args__ = (
        UniqueConstraint("project_id", "control_definition_id", name="uq_project_compliance_controls_definition"),
        CheckConstraint("status IN ('NOT_STARTED', 'IN_PROGRESS', 'SATISFIED', 'NOT_SATISFIED')", name="project_compliance_controls_status"),
        CheckConstraint("applicability IN ('APPLICABLE', 'NOT_APPLICABLE', 'UNDECIDED')", name="project_compliance_controls_applicability"),
        Index("ix_project_compliance_controls_project_framework", "project_id", "framework_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    framework_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_framework_versions.id", ondelete="RESTRICT"), nullable=False)
    control_definition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_control_definitions.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="NOT_STARTED")
    applicability: Mapped[str] = mapped_column(String(20), nullable=False, server_default="UNDECIDED")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ComplianceEvidence(Base):
    __tablename__ = "compliance_evidence"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="compliance_evidence_status"),
        CheckConstraint("(document_version_id IS NOT NULL AND declaration_type IS NULL AND declaration_value IS NULL) OR (document_version_id IS NULL AND declaration_type IS NOT NULL AND declaration_value IS NOT NULL)", name="compliance_evidence_kind"),
        Index("ix_compliance_evidence_project_status", "project_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"))
    declaration_type: Mapped[str | None] = mapped_column(String(100))
    declaration_value: Mapped[str | None] = mapped_column(String(1000))
    declaration_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    revocation_reason: Mapped[str | None] = mapped_column(String(500))


class ControlEvidenceLink(Base):
    __tablename__ = "compliance_control_evidence_links"
    __table_args__ = (
        UniqueConstraint("project_control_id", "evidence_id", name="uq_compliance_control_evidence_link"),
        Index("ix_compliance_control_evidence_links_control", "project_control_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_compliance_controls.id", ondelete="CASCADE"), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_evidence.id", ondelete="RESTRICT"), nullable=False)
    attached_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    attached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ComplianceScoreCalculation(Base):
    """Immutable, explainable result of a versioned deterministic calculation."""
    __tablename__ = "compliance_score_calculations"
    __table_args__ = (
        Index("ix_compliance_score_calculations_project_created", "project_id", "calculated_at"),
        Index("ix_compliance_score_calculations_project_framework", "project_id", "framework_version_id"),
        CheckConstraint("denominator >= 0", name="compliance_score_calculations_denominator_nonnegative"),
        CheckConstraint("numerator >= 0", name="compliance_score_calculations_numerator_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    framework_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("compliance_framework_versions.id", ondelete="RESTRICT"))
    method_key: Mapped[str] = mapped_column(String(100), nullable=False)
    method_version: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    rounding_policy: Mapped[str] = mapped_column(String(80), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    numerator: Mapped[int] = mapped_column(Integer, nullable=False)
    denominator: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(8, 2))
    evidence_coverage: Mapped[float | None] = mapped_column(Numeric(8, 2))
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[dict] = mapped_column(JSONB, nullable=False)
