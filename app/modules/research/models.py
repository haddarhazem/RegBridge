"""Private, versioned research-output metadata."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CHAR, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
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
