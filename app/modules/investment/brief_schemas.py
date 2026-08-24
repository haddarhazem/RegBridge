from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BriefClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=600)
    evidence_refs: list[str] = Field(min_length=1, max_length=10)


MatchingDimension = Literal["sector", "stage", "geography", "technology", "ticket"]
MatchingOutcome = Literal["MATCH", "MISMATCH", "UNKNOWN"]


class MatchingAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: MatchingDimension
    outcome: MatchingOutcome


class BriefHighlight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=600)
    evidence_refs: list[str] = Field(default_factory=list, max_length=10)


class OpportunityBriefGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(min_length=1, max_length=1200)
    thesis_fit_summary: str = Field(min_length=1, max_length=1200)
    investment_highlights: list[BriefHighlight] = Field(default_factory=list, max_length=8)
    matching_acknowledgements: list[MatchingAcknowledgement] = Field(min_length=5, max_length=5)


class BriefEvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investor_thesis: dict
    startup_snapshot: dict
    confirmed_facts: list[dict] = Field(default_factory=list, max_length=50)
    matching_result: dict
    missing_information: list[str] = Field(default_factory=list, max_length=8)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)


class OpportunityBriefContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str
    thesis_fit: list[str]
    investment_highlights: list[str]
    missing_information: list[str]
    disclaimer: str


class OpportunityBriefCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    startup_project_id: uuid.UUID
    investor_thesis_version_id: uuid.UUID | None = None
    matching_run_id: uuid.UUID | None = None


class OpportunityBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    generation_strategy: str
    generation_version: str
    investor_thesis_version_id: uuid.UUID
    startup_project_id: uuid.UUID
    matching_run_id: uuid.UUID | None
    content: OpportunityBriefContent
    created_at: datetime
