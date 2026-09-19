"""Production contracts for regulatory retrieval and grounded answers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegulatoryEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point_id: str = Field(min_length=1, max_length=255)
    rank: int = Field(ge=1, le=5)
    retrieval_score: float
    organization: str = Field(min_length=1, max_length=255)
    source_domain: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=2000)
    parent_url: str | None = Field(default=None, max_length=2000)
    chunk_index: int | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, max_length=500)
    retrieved_at: datetime | None = None
    provenance_type: Literal["QDRANT_CORPUS", "LIVE_AUTHORITATIVE"] = "QDRANT_CORPUS"
    content: str = Field(min_length=1, max_length=12000)


class RegulatoryAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=30000)
    sources: list[str] = Field(default_factory=list, max_length=5)
    evidence: list[RegulatoryEvidence] = Field(default_factory=list, max_length=35)


class RegulatoryQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    subject_type: str | None = None
    subject_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_subject(self) -> "RegulatoryQuestion":
        if (self.subject_type is None) != (self.subject_id is None):
            raise ValueError("subject_type and subject_id must be provided together")
        return self


class RegulatoryPublicResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=30000)
    sources: list[str] = Field(default_factory=list, max_length=5)
