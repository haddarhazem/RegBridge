import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContractAnalysis(Base):
    __tablename__ = "contract_analyses"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="contract_analyses_status"),
        Index("ix_contract_analyses_project_created", "project_id", "created_at"),
        Index("ix_contract_analyses_document_version", "document_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False)
    strategy: Mapped[str] = mapped_column(String(60), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="running")
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    findings: Mapped[list["ContractFinding"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class ContractFinding(Base):
    __tablename__ = "contract_findings"
    __table_args__ = (
        CheckConstraint("finding_type IN ('FINDING', 'RISK', 'RECOMMENDATION', 'UNCERTAINTY')", name="contract_findings_type"),
        CheckConstraint("evidence_start_char >= 0 AND evidence_end_char > evidence_start_char", name="contract_findings_evidence_span"),
        Index("ix_contract_findings_analysis_index", "analysis_id", "finding_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contract_analyses.id", ondelete="CASCADE"), nullable=False)
    finding_index: Mapped[int] = mapped_column(Integer, nullable=False)
    finding_type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str | None] = mapped_column(String(20))
    recommendation: Mapped[str | None] = mapped_column(Text)
    uncertainty: Mapped[str | None] = mapped_column(Text)
    evidence_document_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False)
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    analysis: Mapped[ContractAnalysis] = relationship(back_populates="findings")
