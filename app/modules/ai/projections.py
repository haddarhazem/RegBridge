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
    item_type: Literal[
        "obligation", "recommendation", "uncertainty",
        "administrative", "legal", "finance", "contracts", "privacy",
        "security", "regulatory", "ip", "hr", "launch",
    ]
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
    regulatory_assessment_id: uuid.UUID | None
    assessment_version: int | None = None
    items: list[RoadmapItemProjection] = Field(default_factory=list, max_length=20)


class DocumentProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    title: str = Field(max_length=255)
    document_type: str = Field(max_length=80)
    classification: str = Field(max_length=40)
    visibility: str = Field(max_length=30)
    version_id: uuid.UUID
    version_number: int
    extracted_text: str | None = Field(default=None, max_length=6000)


class ContractClauseProjection(BaseModel):
    """Minimized, version-bound clause detail for the deterministic agent."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    clause_type: str | None = Field(default=None, max_length=120)
    title: str = Field(max_length=200)
    status: str = Field(max_length=30)
    risk_level: str = Field(max_length=30)
    source_text: str = Field(max_length=4000)
    source_location: str | None = Field(default=None, max_length=300)
    verification_status: str = Field(default="UNVERIFIED", max_length=30)
    source_method: str = Field(default="NATIVE", max_length=20)
    evidence_quotes: list[str] = Field(default_factory=list, max_length=4)
    plain_language_summary: str = Field(max_length=2500)
    purpose: str = Field(max_length=1200)
    issues: list[str] = Field(default_factory=list, max_length=8)
    why_it_matters: str | None = Field(default=None, max_length=1800)
    recommendation: str | None = Field(default=None, max_length=2000)
    suggested_revision: str | None = Field(default=None, max_length=3000)
    limitations: list[str] = Field(default_factory=list, max_length=5)


class ContractObservationProjection(BaseModel):
    """Deprecated source-only projection retained for historical trace reads."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    category: str = Field(max_length=80)
    source_quote: str = Field(max_length=4000)
    document_version_id: uuid.UUID
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)


class ContractAnalysisProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    strategy: str | None = Field(default=None, max_length=60)
    status: str = Field(max_length=20)
    summary: str | None = Field(default=None, max_length=4000)
    contract_type: str | None = Field(default=None, max_length=100)
    clauses: list[ContractClauseProjection] = Field(default_factory=list, max_length=20)
    observations: list[ContractObservationProjection] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=5)
