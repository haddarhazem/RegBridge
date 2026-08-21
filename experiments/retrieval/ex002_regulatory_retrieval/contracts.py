from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExpectedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point_id: str | None = None
    source_domain: str | None = None
    url: str | None = None
    parent_url: str | None = None
    chunk_index: int | None = None


class BenchmarkItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=2000)
    topic: str = Field(min_length=1, max_length=120)
    difficulty: str | None = Field(default=None, max_length=20)
    expected_evidence: list[ExpectedEvidence] = Field(default_factory=list, max_length=50)
    annotation_status: Literal["needs_human_validation", "human_validated"]


class CandidateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    question: str
    rank: int = Field(ge=1)
    point_id: str
    score: float
    source_domain: str | None = None
    url: str | None = None
    parent_url: str | None = None
    chunk_index: int | None = None
    content_excerpt: str = Field(max_length=500)
