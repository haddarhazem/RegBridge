"""Bounded EX-003 inputs and outputs.

These contracts deliberately live under experiments. They are not production
API contracts and exclude benchmark labels from verifier input.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    organization: str = Field(min_length=1)
    source_domain: str = Field(min_length=1)
    url: str | None = None
    parent_url: str | None = None
    point_id: str | None = None
    chunk_index: int | None = Field(default=None, ge=0)
    content: str = Field(min_length=1, max_length=12000)


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    material: bool


class VerificationInput(BaseModel):
    """Only fields allowed to reach V1/V2 at inference time."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    public_sources: list[str] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)
    claims: list[ClaimInput] = Field(default_factory=list)
    evidence: list[EvidenceInput] = Field(default_factory=list)


class ClaimAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    support: Literal["supported", "partially_supported", "unsupported", "contradicted", "not_applicable"]
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=500)


class VerificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ClaimAssessment] = Field(default_factory=list)
    citation_issues: list[str] = Field(default_factory=list, max_length=20)
    verdict: Literal["pass", "pass_with_warnings", "block"]
    reasons: list[str] = Field(default_factory=list, max_length=20)
