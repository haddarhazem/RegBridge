import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class EcosystemEvent(Base):
    __tablename__ = "ecosystem_events"
    __table_args__ = (
        CheckConstraint("event_type IN ('event', 'hackathon', 'webinar', 'call_for_projects')", name="ecosystem_events_event_type"),
        CheckConstraint("location_type IN ('online', 'onsite', 'hybrid')", name="ecosystem_events_location_type"),
        CheckConstraint("status IN ('draft', 'active', 'cancelled')", name="ecosystem_events_status"),
        CheckConstraint("starts_at < ends_at", name="ecosystem_events_valid_dates"),
        Index("ix_ecosystem_events_status_starts", "status", "starts_at"),
        Index("ix_ecosystem_events_organizer_status", "organizer_user_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    organizer_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    investor_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("investor_profiles.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location_type: Mapped[str] = mapped_column(String(30), nullable=False)
    location_details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    registration_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class EventRegistration(Base):
    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_registrations_event_user"),
        UniqueConstraint("event_id", "user_id", "project_id", name="uq_event_registrations_event_user_project"),
        CheckConstraint("status IN ('interested', 'registered', 'withdrawn')", name="event_registrations_status"),
        Index("ix_event_registrations_event_status", "event_id", "status"),
        Index("ix_event_registrations_user_status", "user_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ecosystem_events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="registered")
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
