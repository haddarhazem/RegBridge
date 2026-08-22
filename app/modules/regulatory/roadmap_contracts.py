"""API contracts for launch roadmaps."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RoadmapItemType = Literal["obligation", "recommendation", "uncertainty"]
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
    dependency_item_refs: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class LaunchRoadmapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    regulatory_assessment_id: uuid.UUID
    version: int
    status: str
    purpose: RoadmapPurpose
    items: list[RoadmapItemResponse]
    created_at: datetime


class RoadmapGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regulatory_assessment_id: uuid.UUID


class RoadmapItemStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RoadmapItemStatus
