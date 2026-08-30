"""Bounded, provider-neutral projections made available to authorized agents."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AssessmentConclusionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conclusion_id: str = Field(max_length=80)
    category: Literal["obligation", "recommendation", "uncertainty"]
    statement: str = Field(max_length=4000)
    explanation: str | None = Field(default=None, max_length=1000)
    source_refs: list[str] = Field(default_factory=list, max_length=10)


class AssessmentProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    version: int
    snapshot_id: uuid.UUID
    status: str = Field(max_length=30)
    obligations: list[AssessmentConclusionProjection] = Field(default_factory=list, max_length=20)
    recommendations: list[AssessmentConclusionProjection] = Field(default_factory=list, max_length=20)
    uncertainties: list[AssessmentConclusionProjection] = Field(default_factory=list, max_length=20)
    sources: list[str] = Field(default_factory=list, max_length=10)


class RoadmapItemProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    item_type: Literal["obligation", "recommendation", "uncertainty"]
    title: str = Field(max_length=500)
    priority_order: int
    status: Literal["pending", "in_progress", "completed", "skipped"]
    justification: str = Field(max_length=2000)
    source_conclusion_refs: list[str] = Field(default_factory=list, max_length=10)


class RoadmapProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    version: int
    status: str = Field(max_length=20)
    regulatory_assessment_id: uuid.UUID
    assessment_version: int | None = None
    items: list[RoadmapItemProjection] = Field(default_factory=list, max_length=20)
