import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ControlStatus = Literal["NOT_STARTED", "IN_PROGRESS", "SATISFIED", "NOT_SATISFIED"]
Applicability = Literal["APPLICABLE", "NOT_APPLICABLE", "UNDECIDED"]


class FrameworkVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    framework_id: uuid.UUID
    version_identifier: str
    status: str
    effective_date: datetime | None


class FrameworkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    stable_key: str
    name: str
    versions: list[FrameworkVersionResponse] = Field(default_factory=list)


class ControlDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    framework_version_id: uuid.UUID
    stable_key: str
    title: str
    description: str | None
    category: str | None
    source_references: list
    display_order: int


class ProjectControlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    framework_version_id: uuid.UUID
    control_definition_id: uuid.UUID
    status: ControlStatus
    applicability: Applicability
    notes: str | None
    created_at: datetime
    updated_at: datetime
    definition: ControlDefinitionResponse | None = None


class AdoptionCreate(BaseModel):
    framework_version_id: uuid.UUID


class ControlStatePatch(BaseModel):
    status: ControlStatus | None = None
    applicability: Applicability | None = None
    notes: str | None = Field(default=None, max_length=4000)


class EvidenceCreate(BaseModel):
    document_version_id: uuid.UUID | None = None
    declaration_type: str | None = Field(default=None, max_length=100)
    declaration_value: str | None = Field(default=None, max_length=1000)
    declaration_note: str | None = Field(default=None, max_length=4000)
    control_id: uuid.UUID

    @model_validator(mode="after")
    def one_kind(self) -> "EvidenceCreate":
        document = self.document_version_id is not None
        declaration = self.declaration_type is not None and self.declaration_value is not None
        if document == declaration:
            raise ValueError("Provide exactly one document evidence or structured declaration")
        return self


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    document_version_id: uuid.UUID | None
    declaration_type: str | None
    declaration_value: str | None
    declaration_note: str | None
    status: Literal["ACTIVE", "REVOKED"]
    created_by_user_id: uuid.UUID
    created_at: datetime
    revoked_at: datetime | None
    revocation_reason: str | None


class EvidenceRevoke(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AdoptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    framework_version_id: uuid.UUID
    status: Literal["active", "superseded"]
    adopted_by_user_id: uuid.UUID
    adopted_at: datetime
    superseded_at: datetime | None


class ScoreCalculateRequest(BaseModel):
    framework_version_id: uuid.UUID | None = None
    method_version: str = "v1"


class ScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    framework_version_id: uuid.UUID | None
    method_key: str
    method_version: str
    evidence_policy_version: str
    rounding_policy: str
    calculated_at: datetime
    numerator: int
    denominator: int
    score: float | None
    evidence_coverage: float | None
    input_snapshot: dict
    explanation: dict
