import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class ContactRequest(Base):
    __tablename__ = "contact_requests"
    __table_args__ = (
        CheckConstraint("target_type IN ('project', 'investor_profile', 'researcher_profile', 'research_output')", name="contact_requests_target_type"),
        CheckConstraint("status IN ('pending', 'accepted', 'declined', 'cancelled')", name="contact_requests_status"),
        Index("ix_contact_requests_requester_status", "requester_user_id", "status"),
        Index("ix_contact_requests_target", "target_type", "target_id", "status"),
        Index("ux_contact_requests_pending", "requester_user_id", "target_type", "target_id", text("coalesce(source_project_id, '00000000-0000-0000-0000-000000000000'::uuid)"), unique=True, postgresql_where=text("status = 'pending'")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    requester_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    source_project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class ContactPoint(Base):
    __tablename__ = "contact_points"
    __table_args__ = (CheckConstraint("channel IN ('EMAIL', 'WEBSITE')", name="contact_points_channel"), Index("ix_contact_points_owner_active", "owner_user_id", "active"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class ContactConsent(Base):
    __tablename__ = "contact_consents"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'revoked')", name="contact_consents_status"),
        UniqueConstraint("request_id", "contact_point_id", "status", name="uq_contact_consents_request_point_status"),
        Index("ix_contact_consents_request_status", "request_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact_requests.id", ondelete="CASCADE"), nullable=False)
    contact_point_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contact_points.id", ondelete="RESTRICT"), nullable=False)
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    value_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
