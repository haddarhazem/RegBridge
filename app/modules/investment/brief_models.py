"""Persistence model for immutable investor opportunity brief generations."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvestorOpportunityBriefRun(Base):
    __tablename__ = "investor_opportunity_brief_runs"
    __table_args__ = (
        Index("ix_investor_opportunity_brief_runs_investor_created", "investor_user_id", text("created_at DESC")),
        Index("ix_investor_opportunity_brief_runs_startup_created", "startup_project_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    investor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    investor_thesis_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investor_thesis_versions.id", ondelete="RESTRICT"), nullable=False)
    startup_project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    matching_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("investment_matching_runs.id", ondelete="RESTRICT"))
    startup_snapshot_revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("startup_profile_revisions.id", ondelete="RESTRICT"))
    investor_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    startup_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence_bundle: Mapped[dict] = mapped_column(JSONB, nullable=False)
    matching_result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generation_strategy: Mapped[str] = mapped_column(String(60), nullable=False)
    generation_version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="DRAFT")
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
