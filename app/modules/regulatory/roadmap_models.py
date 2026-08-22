"""Persistence models for versioned entrepreneur launch roadmaps."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LaunchRoadmap(Base):
    __tablename__ = "launch_roadmaps"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_launch_roadmaps_project_version"),
        Index("ix_launch_roadmaps_project_created", "project_id", "created_at"),
        CheckConstraint("status IN ('active', 'archived')", name="launch_roadmaps_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    regulatory_assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regulatory_assessments.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LaunchRoadmapItem(Base):
    __tablename__ = "launch_roadmap_items"
    __table_args__ = (
        Index("ix_launch_roadmap_items_roadmap_order", "roadmap_id", "priority_order"),
        CheckConstraint("item_type IN ('obligation', 'recommendation', 'uncertainty')", name="launch_roadmap_items_type"),
        CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'skipped')", name="launch_roadmap_items_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    roadmap_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("launch_roadmaps.id", ondelete="CASCADE"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    justification: Mapped[str] = mapped_column(String(2000), nullable=False)
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    source_conclusion_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    dependency_item_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
