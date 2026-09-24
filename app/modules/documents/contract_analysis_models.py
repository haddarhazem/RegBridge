"""Persistence for versioned, evidence-linked contract analysis.

The tables follow the V2.1 schema.  ``source_refs`` contains a bounded source
locator and the deterministic explanation derived from that locator; it never
duplicates the full uploaded contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContractAnalysis(Base):
    __tablename__ = "contract_analyses"
    __table_args__ = (
        CheckConstraint("overall_risk_level IN ('low', 'medium', 'high', 'critical', 'unknown')", name="contract_analyses_overall_risk_level"),
        UniqueConstraint("document_version_id", "analysis_version", name="uq_contract_analyses_version"),
        Index("ix_contract_analyses_project_id", "project_id"),
        Index("ix_contract_analyses_document_version", "document_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id"), nullable=False)
    analysis_version: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_type: Mapped[str | None] = mapped_column(String(100))
    overall_risk_level: Mapped[str | None] = mapped_column(String(30))
    summary: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    missing_context: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    clauses: Mapped[list["ContractClause"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class ContractClause(Base):
    __tablename__ = "contract_clauses"
    __table_args__ = (UniqueConstraint("contract_analysis_id", "clause_order", name="uq_contract_clauses_analysis_order"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    contract_analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contract_analyses.id", ondelete="CASCADE"), nullable=False)
    clause_order: Mapped[int] = mapped_column(Integer, nullable=False)
    clause_type: Mapped[str | None] = mapped_column(String(120))
    heading: Mapped[str | None] = mapped_column(Text)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False, server_default="unknown")
    finding: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(Text)
    source_refs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    analysis: Mapped[ContractAnalysis] = relationship(back_populates="clauses")


# Compatibility import only. The persisted V2.1 table is ``contract_clauses``.
ContractFinding = ContractClause
