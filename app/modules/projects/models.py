import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_owner_user_id", "owner_user_id"),
        Index("ix_projects_project_type", "project_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    project_type: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    user_goal: Mapped[str | None] = mapped_column(Text)
    activity: Mapped[str | None] = mapped_column(String(500))
    sector: Mapped[str | None] = mapped_column(String(160))
    technology: Mapped[str | None] = mapped_column(String(500))
    data_context: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(160))
    current_progress: Mapped[str | None] = mapped_column(String(80))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, server_default="FR")
    target_market: Mapped[str | None] = mapped_column(String(120), nullable=True, server_default="France")
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default="fr")
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, server_default="private")
    onboarding_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="in_progress")
    confirmed_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    members: Mapped[list["ProjectMember"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    facts: Mapped[list["ProjectFact"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectFact(Base):
    __tablename__ = "project_facts"
    __table_args__ = (
        UniqueConstraint("project_id", "domain", "value", "status", name="uq_project_facts_active_value"),
        Index("ix_project_facts_project_status", "project_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    domain: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    origin: Mapped[str] = mapped_column(String(30), nullable=False, server_default="inferred")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending_confirmation")
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    uncertainty: Mapped[str] = mapped_column(String(10), nullable=False, server_default="high")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    project: Mapped[Project] = relationship(back_populates="facts")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        Index("ix_project_members_user_id", "user_id"),
        Index("ix_project_members_project_id_status", "project_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    member_role: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    project: Mapped[Project] = relationship(back_populates="members", foreign_keys=[project_id])


class StartupResearchNeed(Base):
    __tablename__ = "startup_research_needs"
    __table_args__ = (Index("ix_startup_research_needs_project", "project_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StartupResearchNeedVersion(Base):
    __tablename__ = "startup_research_need_versions"
    __table_args__ = (UniqueConstraint("need_id", "version_number", name="uq_startup_research_need_versions_number"), Index("ix_startup_research_need_versions_need", "need_id", "version_number"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    need_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("startup_research_needs.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    domains: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    technologies: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    research_problem: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResearchMatchRun(Base):
    __tablename__ = "research_match_runs"
    __table_args__ = (Index("ix_research_match_runs_need_version", "need_version_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    need_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("startup_research_need_versions.id", ondelete="RESTRICT"), nullable=False)
    algorithm_id: Mapped[str] = mapped_column(String(80), nullable=False, server_default="sparse_research_matching_s3")
    algorithm_version: Mapped[str] = mapped_column(String(30), nullable=False, server_default="1")
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="COMPLETED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResearchMatchResult(Base):
    __tablename__ = "research_match_results"
    __table_args__ = (UniqueConstraint("run_id", "rank", name="uq_research_match_results_rank"), Index("ix_research_match_results_run", "run_id", "rank"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_match_runs.id", ondelete="CASCADE"), nullable=False)
    research_discovery_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_discovery_versions.id", ondelete="RESTRICT"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    ranking_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="MATCH")
    reason_codes: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    startup_field_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    research_field_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    uncertainty_codes: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
