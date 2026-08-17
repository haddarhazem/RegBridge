import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Classification = Literal["public", "internal", "confidential", "highly_confidential"]
DocumentVisibility = Literal["private", "project_members", "shared", "public"]
JobType = Literal["extract_text", "classify", "embed", "analyze_contract", "index_research", "generate_pitch"]


class DocumentResponse(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    document_type: str
    classification: Classification
    visibility: DocumentVisibility
    processing_status: str
    current_version_id: uuid.UUID | None
    deleted_at: datetime | None


class DocumentVersionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    malware_scan_status: str
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    version: DocumentVersionResponse


class ProcessingJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_type: JobType
    idempotency_key: str = Field(min_length=1, max_length=200)


class ProcessingJobResponse(BaseModel):
    id: uuid.UUID
    document_version_id: uuid.UUID
    job_type: JobType
    idempotency_key: str
    status: str
