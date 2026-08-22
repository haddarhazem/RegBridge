"""API contracts for versioned regulatory assessments."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AssessmentConclusion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=4000)
    category: Literal["obligation", "recommendation", "uncertainty"]
    source_refs: list[str] = Field(default_factory=list, max_length=10)
    explanation: str | None = Field(default=None, max_length=1000)


class AssessmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(default="", max_length=30000)
    obligations: list[AssessmentConclusion] = Field(default_factory=list, max_length=50)
    recommendations: list[AssessmentConclusion] = Field(default_factory=list, max_length=50)
    uncertainties: list[AssessmentConclusion] = Field(default_factory=list, max_length=50)
    sources: list[str] = Field(default_factory=list, max_length=10)


class AssessmentSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    facts: list[dict]
    snapshot_hash: str
    created_at: datetime


class RegulatoryAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    snapshot_id: uuid.UUID
    status: str
    result: AssessmentResult
    verification_verdict: str | None
    verification_reasons: list[str]
    created_at: datetime


class AssessmentGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(default="Évaluez les obligations réglementaires principales applicables à cette idée.", min_length=1, max_length=4000)
