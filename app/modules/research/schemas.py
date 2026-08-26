from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResearcherProfileUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affiliation: str | None = Field(default=None, max_length=255)
    scientific_domains: list[str] = Field(default_factory=list, max_length=20)


class ResearcherProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    affiliation: str | None
    scientific_domains: list[str]
    created_at: datetime
    updated_at: datetime


class ResearchOutputCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    authors: list[str] = Field(min_length=1, max_length=100)
    rights_holder: str | None = Field(default=None, max_length=500)
    licence: str | None = Field(default=None, max_length=255)
    visibility: Literal["private", "public"] = "private"

    @field_validator("authors")
    @classmethod
    def validate_authors(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("Authors must contain non-empty names")
        return cleaned


class ResearchOutputResponse(BaseModel):
    id: uuid.UUID
    researcher_profile_id: uuid.UUID
    title: str
    authors: list[str]
    rights_holder: str | None
    licence: str | None
    visibility: Literal["private", "public"]
    rights_metadata_status: Literal["COMPLETE", "INCOMPLETE"]
    missing_rights_fields: list[str]
    publication_ready: bool
    created_at: datetime
    updated_at: datetime


class ResearchOutputVersionResponse(BaseModel):
    id: uuid.UUID
    research_output_id: uuid.UUID
    version_number: int
    uploaded_by_user_id: uuid.UUID
    document_version_id: uuid.UUID
    mime_type: str
    size_bytes: int
    content_hash: str
    original_filename: str
    created_at: datetime


class ResearchEvidenceResponse(BaseModel):
    segment_id: str
    locator: dict


class ResearchExtractionItemResponse(BaseModel):
    field: str
    status: str
    source_text: str | None
    item_order: int
    evidence: list[ResearchEvidenceResponse]


class ResearchExtractionResponse(BaseModel):
    id: uuid.UUID
    research_output_id: uuid.UUID
    research_output_version_id: uuid.UUID
    document_version_id: uuid.UUID
    source_sha256: str
    strategy: str
    strategy_version: str
    provider: str
    model: str
    status: str
    regbridge_abstract: str
    created_at: datetime
    completed_at: datetime | None
    items: list[ResearchExtractionItemResponse]


class ResearchDiscoveryInitialize(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extraction_run_id: uuid.UUID


class ResearchDiscoveryCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: dict[str, list[str]] = Field(default_factory=dict)
    visibility: dict[str, Literal["PRIVATE", "PUBLIC", "MATCHABLE"]] = Field(default_factory=dict)
    base_version_id: uuid.UUID


class ResearchDiscoveryResponse(BaseModel):
    id: uuid.UUID
    discovery_id: uuid.UUID
    version_number: int
    extraction_run_id: uuid.UUID
    research_output_version_id: uuid.UUID
    document_version_id: uuid.UUID
    source_sha256: str
    status: Literal["DRAFT", "APPROVED"]
    content: dict
    visibility: dict
    approved_by_user_id: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime


ResearchAccessScope = Literal["CONTACT", "DISCOVERY_READ", "FULL_DOCUMENT_READ", "COLLABORATION"]
ResearchAccessStatus = Literal["PENDING", "ACCEPTED", "LIMITED", "REFUSED", "REVOKED"]


class ResearchAccessRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_output_id: uuid.UUID
    research_output_version_id: uuid.UUID | None = None
    research_discovery_version_id: uuid.UUID | None = None
    requester_project_id: uuid.UUID | None = None
    requested_scopes: list[ResearchAccessScope] = Field(min_length=1, max_length=4)
    message: str | None = Field(default=None, max_length=1000)


class ResearchAccessDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    granted_scopes: list[ResearchAccessScope] | None = None


class ResearchAccessRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    research_output_id: uuid.UUID
    research_output_version_id: uuid.UUID | None
    research_discovery_version_id: uuid.UUID | None
    requester_user_id: uuid.UUID
    requester_project_id: uuid.UUID | None
    requested_scopes: list[str]
    granted_scopes: list[str] | None
    status: ResearchAccessStatus
    message: str | None
    decided_by_user_id: uuid.UUID | None
    decided_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime
