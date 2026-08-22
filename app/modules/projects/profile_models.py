"""Structured startup profile fields and immutable profile revisions."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StartupProfile(Base):
    __tablename__ = "startup_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    fields: Mapped[list["StartupProfileField"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    revisions: Mapped[list["StartupProfileRevision"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class StartupProfileField(Base):
    __tablename__ = "startup_profile_fields"
    __table_args__ = (
        UniqueConstraint("profile_id", "field_name", name="uq_startup_profile_fields_name"),
        CheckConstraint("visibility IN ('PUBLIC', 'INVESTOR_SHARED', 'PRIVATE')", name="startup_profile_fields_visibility"),
        Index("ix_startup_profile_fields_profile_visibility", "profile_id", "visibility"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("startup_profiles.id", ondelete="CASCADE"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[object | None] = mapped_column(JSONB)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    profile: Mapped[StartupProfile] = relationship(back_populates="fields")


class StartupProfileRevision(Base):
    __tablename__ = "startup_profile_revisions"
    __table_args__ = (
        UniqueConstraint("profile_id", "revision_number", name="uq_startup_profile_revisions_number"),
        Index("ix_startup_profile_revisions_profile_created", "profile_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("startup_profiles.id", ondelete="CASCADE"), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    profile: Mapped[StartupProfile] = relationship(back_populates="revisions")
