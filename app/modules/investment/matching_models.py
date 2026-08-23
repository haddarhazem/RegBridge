import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MatchingRun(Base):
    __tablename__ = "investment_matching_runs"
    __table_args__ = (
        Index("ix_investment_matching_runs_investor_created", "investor_user_id", text("created_at DESC")),
        Index("ix_investment_matching_runs_startup", "startup_project_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    investor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    investor_thesis_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investor_thesis_versions.id", ondelete="RESTRICT"), nullable=False)
    startup_project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    startup_snapshot_revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("startup_profile_revisions.id", ondelete="RESTRICT"))
    investor_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    startup_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    matching_method: Mapped[str] = mapped_column(String(80), nullable=False)
    matching_method_version: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(8, 6))
    score_formula: Mapped[str] = mapped_column(String(255), nullable=False)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    explanation_mode: Mapped[str] = mapped_column(String(40), nullable=False, server_default="deterministic_fallback")
    llm_provider: Mapped[str | None] = mapped_column(String(80))
    llm_model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
