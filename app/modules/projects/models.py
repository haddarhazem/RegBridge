import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_owner_user_id", "owner_user_id"),
        Index("ix_projects_project_type", "project_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    project_type: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    user_goal: Mapped[str | None] = mapped_column(Text)
    activity: Mapped[str | None] = mapped_column(String(500))
    sector: Mapped[str | None] = mapped_column(String(160))
    technology: Mapped[str | None] = mapped_column(String(500))
    data_context: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(160))
    current_progress: Mapped[str | None] = mapped_column(String(80))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, server_default="FR")
    target_market: Mapped[str | None] = mapped_column(String(120), nullable=True, server_default="France")
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default="fr")
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, server_default="private")
    onboarding_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="in_progress")
    confirmed_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    members: Mapped[list["ProjectMember"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        Index("ix_project_members_user_id", "user_id"),
        Index("ix_project_members_project_id_status", "project_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    member_role: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    project: Mapped[Project] = relationship(back_populates="members", foreign_keys=[project_id])
