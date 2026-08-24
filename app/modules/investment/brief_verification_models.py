"""Historical factual verification records for investor opportunity briefs."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BriefVerificationRun(Base):
    __tablename__ = "investor_opportunity_brief_verification_runs"
    __table_args__ = (
        Index("ix_brief_verification_runs_brief_created", "brief_run_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    brief_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investor_opportunity_brief_runs.id", ondelete="RESTRICT"), nullable=False)
    brief_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("investor_opportunity_brief_versions.id", ondelete="RESTRICT"))
    verifier_strategy: Mapped[str] = mapped_column(String(60), nullable=False)
    verifier_version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BriefClaimVerification(Base):
    __tablename__ = "investor_opportunity_brief_claim_verifications"
    __table_args__ = (
        Index("ix_brief_claim_verifications_run", "verification_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    verification_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investor_opportunity_brief_verification_runs.id", ondelete="CASCADE"), nullable=False)
    claim_id: Mapped[str] = mapped_column(String(120), nullable=False)
    section: Mapped[str] = mapped_column(String(80), nullable=False)
    claim_text: Mapped[str] = mapped_column(String(1200), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(80), nullable=False)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
