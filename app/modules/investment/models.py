import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class InvestorProfile(Base):
    __tablename__ = "investor_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_investor_profiles_user"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("investor_thesis_versions.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class InvestorThesisVersion(Base):
    __tablename__ = "investor_thesis_versions"
    __table_args__ = (
        UniqueConstraint("investor_profile_id", "version_number", name="uq_investor_thesis_versions_number"),
        Index("ix_investor_thesis_versions_profile_created", "investor_profile_id", "created_at"),
        CheckConstraint("ticket_min IS NULL OR ticket_min >= 0", name="investor_thesis_ticket_min_nonnegative"),
        CheckConstraint("ticket_max IS NULL OR ticket_max >= 0", name="investor_thesis_ticket_max_nonnegative"),
        CheckConstraint("ticket_min IS NULL OR ticket_max IS NULL OR ticket_min <= ticket_max", name="investor_thesis_ticket_range"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    investor_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investor_profiles.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sectors: Mapped[list | None] = mapped_column(JSONB)
    stages: Mapped[list | None] = mapped_column(JSONB)
    geographies: Mapped[list | None] = mapped_column(JSONB)
    technologies: Mapped[list | None] = mapped_column(JSONB)
    ticket_min: Mapped[float | None] = mapped_column(Numeric(18, 2))
    ticket_max: Mapped[float | None] = mapped_column(Numeric(18, 2))
    ticket_currency: Mapped[str | None] = mapped_column(String(3))
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="USER_DECLARED")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class InvestmentOpportunity(Base):
    __tablename__ = "investment_opportunities"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    investor_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investor_profiles.id", ondelete="CASCADE"), nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED')", name="investment_opportunities_status"),
        CheckConstraint("visibility IN ('AUTHENTICATED', 'PUBLIC')", name="investment_opportunities_visibility"),
        Index("ix_investment_opportunities_investor_status", "investor_profile_id", "status"),
        ForeignKeyConstraint(["current_version_id", "id"], ["investment_opportunity_versions.id", "investment_opportunity_versions.opportunity_id"], name="fk_investment_opportunities_current_version", ondelete="RESTRICT"),
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, server_default="AUTHENTICATED")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="DRAFT")
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class InvestmentOpportunityVersion(Base):
    __tablename__ = "investment_opportunity_versions"
    __table_args__ = (UniqueConstraint("opportunity_id", "version_number", name="uq_investment_opportunity_versions_number"), UniqueConstraint("id", "opportunity_id", name="uq_investment_opportunity_versions_id_opportunity"), Index("ix_investment_opportunity_versions_opportunity_created", "opportunity_id", "created_at"), CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED')", name="investment_opportunity_versions_status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investment_opportunities.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    visibility: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
