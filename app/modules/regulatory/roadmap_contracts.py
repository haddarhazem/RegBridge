"""API contracts for launch roadmaps."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RoadmapItemType = Literal[
    "obligation", "recommendation", "uncertainty",  # legacy roadmap versions
    "administrative", "legal", "finance", "contracts", "privacy",
    "security", "regulatory", "ip", "hr", "launch",
]
RoadmapItemOrigin = Literal["BASELINE", "PROJECT_CONTEXT", "REGULATORY_ASSESSMENT"]
RoadmapItemStatus = Literal["pending", "in_progress", "completed", "skipped"]
RoadmapPurpose = Literal["creation", "compliance"]


class RoadmapItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    roadmap_id: uuid.UUID
    item_type: RoadmapItemType
    title: str
    justification: str
    priority_order: int
    status: RoadmapItemStatus
    source_conclusion_refs: list[str]
    origins: list[RoadmapItemOrigin]
    dependency_item_refs: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class LaunchRoadmapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    regulatory_assessment_id: uuid.UUID | None
    regulatory_coverage: Literal["enriched", "incomplete"]
    version: int
    status: str
    purpose: RoadmapPurpose
    items: list[RoadmapItemResponse]
    created_at: datetime


class RoadmapGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regulatory_assessment_id: uuid.UUID | None = None


class RoadmapItemStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RoadmapItemStatus
