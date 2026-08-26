"""Private, versioned research-output metadata."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CHAR, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearcherProfile(Base):
    __tablename__ = "researcher_profiles"
    __table_args__ = (Index("ix_researcher_profiles_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    affiliation: Mapped[str | None] = mapped_column(String(255))
    scientific_domains: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ResearchOutput(Base):
    __tablename__ = "research_outputs"
    __table_args__ = (
        CheckConstraint("visibility IN ('private', 'public')", name="research_outputs_visibility"),
        CheckConstraint("rights_metadata_status IN ('COMPLETE', 'INCOMPLETE')", name="research_outputs_rights_status"),
        Index("ix_research_outputs_profile_created", "researcher_profile_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    researcher_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[list] = mapped_column(JSONB, nullable=False)
    rights_holder: Mapped[str | None] = mapped_column(String(500))
    licence: Mapped[str | None] = mapped_column(String(255))
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, server_default="private")
    rights_metadata_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="INCOMPLETE")
    publication_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ResearchOutputVersion(Base):
    __tablename__ = "research_output_versions"
    __table_args__ = (
        UniqueConstraint("research_output_id", "version_number", name="uq_research_output_versions_number"),
        UniqueConstraint("document_version_id", name="uq_research_output_versions_document_version"),
        CheckConstraint("version_number > 0", name="research_output_versions_positive_number"),
        CheckConstraint("length(content_hash) = 64", name="research_output_versions_hash_length"),
        Index("ix_research_output_versions_output_created", "research_output_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    research_output_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_outputs.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResearchExtractionRun(Base):
    __tablename__ = "research_extraction_runs"
    __table_args__ = (
        CheckConstraint("strategy = 'extractive_evidence_locked'", name="research_extraction_runs_strategy"),
        CheckConstraint("status IN ('GENERATED', 'FAILED')", name="research_extraction_runs_status"),
        Index("ix_research_extraction_runs_version_created", "research_output_version_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    research_output_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_outputs.id", ondelete="CASCADE"), nullable=False)
    research_output_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_output_versions.id", ondelete="RESTRICT"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False)
    source_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    segmenter_version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    regbridge_abstract: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResearchExtractionItem(Base):
    __tablename__ = "research_extraction_items"
    __table_args__ = (
        CheckConstraint("field IN ('domains','technologies','research_problem','methodology','main_results','explicit_applications','keywords','limitations')", name="research_extraction_items_field"),
        CheckConstraint("status IN ('SUPPORTED', 'NOT_AVAILABLE')", name="research_extraction_items_status"),
        Index("ix_research_extraction_items_run_field", "run_id", "field"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_extraction_runs.id", ondelete="CASCADE"), nullable=False)
    field: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_text: Mapped[str | None] = mapped_column(Text)
    item_order: Mapped[int] = mapped_column(Integer, nullable=False)


class ResearchEvidenceRef(Base):
    __tablename__ = "research_evidence_refs"
    __table_args__ = (Index("ix_research_evidence_refs_item_order", "item_id", "item_order"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_extraction_items.id", ondelete="CASCADE"), nullable=False)
    research_output_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_output_versions.id", ondelete="RESTRICT"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False)
    segment_id: Mapped[str] = mapped_column(String(40), nullable=False)
    locator: Mapped[dict] = mapped_column(JSONB, nullable=False)
    item_order: Mapped[int] = mapped_column(Integer, nullable=False)


class ResearchDiscovery(Base):
    __tablename__ = "research_discoveries"
    __table_args__ = (UniqueConstraint("research_output_id", name="uq_research_discoveries_output"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    research_output_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_outputs.id", ondelete="CASCADE"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResearchDiscoveryVersion(Base):
    __tablename__ = "research_discovery_versions"
    __table_args__ = (
        UniqueConstraint("discovery_id", "version_number", name="uq_research_discovery_versions_number"),
        CheckConstraint("status IN ('DRAFT', 'APPROVED')", name="research_discovery_versions_status"),
        Index("ix_research_discovery_versions_current", "discovery_id", "version_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    discovery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_discoveries.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_extraction_runs.id", ondelete="RESTRICT"), nullable=False)
    research_output_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_output_versions.id", ondelete="RESTRICT"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False)
    source_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    visibility: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="DRAFT")
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
