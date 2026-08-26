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
