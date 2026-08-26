import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class InvestorShareGrant(Base):
    __tablename__ = "investor_share_grants"
    __table_args__ = (
        CheckConstraint("resource_type IN ('STARTUP_PROFILE_REVISION', 'COMPLIANCE_SCORE_CALCULATION', 'DOCUMENT_VERSION', 'INVESTOR_OPPORTUNITY_BRIEF_VERSION', 'RESEARCH_OUTPUT_VERSION', 'RESEARCH_DISCOVERY_VERSION')", name="investor_share_grants_resource_type"),
        CheckConstraint("scope IN ('READ', 'CONTACT', 'DISCOVERY_READ', 'FULL_DOCUMENT_READ', 'COLLABORATION')", name="investor_share_grants_scope"),
        CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="investor_share_grants_status"),
        Index("ix_investor_share_grants_recipient_status", "recipient_user_id", "status"),
        Index("ix_investor_share_grants_project_status", "project_id", "status"),
        Index("ix_investor_share_grants_resource", "resource_type", "resource_id", "resource_version_id"),
        Index("ix_investor_share_grants_request", "request_id", "status"),
        Index("ux_investor_share_grants_active_exact", "project_id", "recipient_user_id", "resource_type", "resource_id", text("coalesce(resource_version_id, '00000000-0000-0000-0000-000000000000'::uuid)"), "scope", unique=True, postgresql_where=text("status = 'ACTIVE'")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    resource_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    scope: Mapped[str] = mapped_column(String(30), nullable=False, server_default="READ")
    request_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("research_access_requests.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
