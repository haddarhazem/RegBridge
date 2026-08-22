import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractAnalysisResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    strategy: str
    status: Literal["running", "completed", "failed"]
    provider: str | None
    model: str | None
    error_code: str | None
    created_at: datetime
    findings: list["ContractFindingResponse"] = Field(default_factory=list)
    observations: list["ContractObservationResponse"] = Field(default_factory=list)
    risks: list[dict] = Field(default_factory=list)
    recommendations: list[dict] = Field(default_factory=list)
    semantic_interpretation_available: bool = False
    limitations: list[str] = Field(default_factory=lambda: ["Automated semantic risk and recommendation interpretation is not included."])


class ContractFindingResponse(BaseModel):
    id: uuid.UUID
    finding_index: int
    finding_type: Literal["FINDING", "RISK", "RECOMMENDATION", "UNCERTAINTY"]
    category: str
    statement: str
    risk_level: str | None
    recommendation: str | None
    uncertainty: str | None
    evidence_document_version_id: uuid.UUID
    evidence_quote: str
    evidence_start_char: int
    evidence_end_char: int


class ContractObservationResponse(BaseModel):
    id: uuid.UUID
    observation_index: int
    suggested_category: str
    source_quote: str
    document_version_id: uuid.UUID
    start_char: int
    end_char: int


ContractAnalysisResponse.model_rebuild()
