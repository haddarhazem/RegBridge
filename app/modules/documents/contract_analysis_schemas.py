from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.contract_risk import ContractRiskIndex


RiskLevel = Literal["low", "medium", "high", "critical", "informational", "unknown"]
ClauseStatus = Literal["FOUND", "MISSING", "AMBIGUOUS", "CONTRADICTORY", "OTHER", "NOT_APPLICABLE"]


class ContractEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_version_id: uuid.UUID
    quote: str
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    locator: str
    section_id: str = "legacy-section"
    page_start: int | None = None
    page_end: int | None = None
    source_method: Literal["NATIVE", "OCR", "MIXED"] = "NATIVE"
    verification_status: Literal["VERIFIED", "PARTIALLY_VERIFIED", "UNVERIFIED"] = "UNVERIFIED"


class ContractPartyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: str | None = None
    source_section_id: str
    source_quote: str
    page_number: int


class ContractClauseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    clause_order: int
    clause_type: str | None
    title: str
    status: ClauseStatus
    source_text: str
    source_location: str | None
    evidence: list[ContractEvidenceResponse] = Field(default_factory=list)
    verification_status: Literal["VERIFIED", "PARTIALLY_VERIFIED", "UNVERIFIED"] = "UNVERIFIED"
    source_method: Literal["NATIVE", "OCR", "MIXED"] = "NATIVE"
    plain_language_summary: str
    purpose: str
    what_the_clause_requires: str | None
    affected_party: str | None
    risk_level: RiskLevel
    issues: list[str] = Field(default_factory=list)
    why_it_matters: str | None
    ambiguities: list[str] = Field(default_factory=list)
    missing_elements: list[str] = Field(default_factory=list)
    potential_consequences: list[str] = Field(default_factory=list)
    recommendation: str | None
    suggested_revision: str | None
    related_clauses: list[str] = Field(default_factory=list)
    confidence: float | None
    limitations: list[str] = Field(default_factory=list)


class ContractAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    analysis_version: int
    contract_type: str | None
    parties: list[str] = Field(default_factory=list)
    party_details: list[ContractPartyResponse] = Field(default_factory=list)
    effective_dates: list[str] = Field(default_factory=list)
    overall_risk_level: RiskLevel
    summary: str | None
    recommendations: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    status: Literal["running", "completed", "partial", "failed"]
    error_code: str | None = None
    created_at: datetime
    clauses: list[ContractClauseResponse] = Field(default_factory=list)
    risk_index: ContractRiskIndex
    limitations: list[str] = Field(default_factory=lambda: ["L'analyse automatique aide à la revue et ne remplace pas un avis juridique."])
