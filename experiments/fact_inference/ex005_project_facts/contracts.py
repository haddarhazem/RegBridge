from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FactDomain = Literal["activity", "sector", "technology", "data", "market", "location"]
Uncertainty = Literal["high", "medium", "low"]
FactOrigin = Literal["inferred", "user_declared"]
FactStatus = Literal["pending_confirmation", "confirmed", "corrected", "deleted"]


class FactProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_field: Literal["description", "activity", "sector", "technology", "data", "market", "location"]
    excerpt: str = Field(min_length=1, max_length=300)
    rule: str | None = Field(default=None, max_length=120)


class ExtractedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: FactDomain
    value: str = Field(min_length=1, max_length=500)
    origin: FactOrigin = "inferred"
    status: FactStatus = "pending_confirmation"
    provenance: FactProvenance
    uncertainty: Uncertainty


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: list[ExtractedFact] = Field(default_factory=list, max_length=30)
