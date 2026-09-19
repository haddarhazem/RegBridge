import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.ai.pipeline_types import EvidenceStatus, PipelineStage


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    subject_type: Literal["project"] | None = None
    subject_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_subject(self) -> "ConversationCreate":
        if (self.subject_type is None) != (self.subject_id is None):
            raise ValueError("subject_type and subject_id must be provided together")
        return self


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    document_id: uuid.UUID | None = None
    document_version_id: uuid.UUID | None = None
    analysis_id: uuid.UUID | None = None
    # Accepted only for compatibility with clients that send a role; the server ignores it.
    role: str | None = Field(default=None, exclude=True)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    role: str
    content: str
    content_json: dict[str, Any] | list[Any] | None
    status: str
    parent_message_id: uuid.UUID | None
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    subject_type: str | None
    subject_id: uuid.UUID | None
    status: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    messages: list[MessageResponse] = []


class CopilotTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID
    user_message: MessageResponse
    assistant_message: MessageResponse
    orchestration_status: Literal["succeeded", "partial", "failed"]
    sources: list[str] = Field(default_factory=list, max_length=50)
    references: list[str] = Field(default_factory=list, max_length=10)
    warnings: list[str] = Field(default_factory=list, max_length=10)


class CopilotStageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: PipelineStage
    status: Literal["not_started", "running", "succeeded", "failed", "cancelled"]
    duration_ms: float | None = Field(default=None, ge=0)


class CopilotDiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_domains: list[str] = Field(default_factory=list, max_length=6)
    covered_domains: list[str] = Field(default_factory=list, max_length=6)
    missing_domains: list[str] = Field(default_factory=list, max_length=6)
    retrieved_chunk_count: int | None = Field(default=None, ge=0, le=5)
    provider: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=120)
    verification_verdict: str | None = Field(default=None, max_length=40)
    verification_reason: str | None = Field(default=None, max_length=500)
    semantic_claim_count: int | None = Field(default=None, ge=0, le=50)
    supported_claim_count: int | None = Field(default=None, ge=0, le=50)
    unsupported_claim_count: int | None = Field(default=None, ge=0, le=50)
    unverified_claim_count: int | None = Field(default=None, ge=0, le=50)
    failure_code: str | None = Field(default=None, max_length=80)
    resolution_source: str | None = Field(default=None, max_length=80)
    matched_signals: list[str] = Field(default_factory=list, max_length=12)
    needs_clarification: bool = False
    question_scope: str | None = Field(default=None, max_length=40)
    scope_signals: list[str] = Field(default_factory=list, max_length=12)
    scope_supported: bool | None = None
    scope_support_reason: str | None = Field(default=None, max_length=1000)
    initial_evidence_count: int | None = Field(default=None, ge=0, le=5)
    initial_evidence_status: EvidenceStatus | None = None
    initial_covered_domains: list[str] = Field(default_factory=list, max_length=6)
    initial_missing_domains: list[str] = Field(default_factory=list, max_length=6)
    initial_question_scope: str | None = Field(default=None, max_length=40)
    initial_scope_supported: bool | None = None
    initial_scope_support_reason: str | None = Field(default=None, max_length=1000)
    fallback_attempted: bool = False
    fallback_domains: list[str] = Field(default_factory=list, max_length=6)
    fallback_evidence_count: int | None = Field(default=None, ge=0, le=30)
    fallback_unique_evidence_count: int | None = Field(default=None, ge=0, le=30)
    fallback_failed_domains: list[str] = Field(default_factory=list, max_length=6)
    fallback_failure_count: int | None = Field(default=None, ge=0, le=6)
    authoritative_fallback_attempted: bool = False
    authoritative_fallback_domains: list[str] = Field(default_factory=list, max_length=6)
    authoritative_sources_attempted: list[str] = Field(default_factory=list, max_length=2)
    authoritative_sources_succeeded: list[str] = Field(default_factory=list, max_length=2)
    authoritative_sources_failed: list[str] = Field(default_factory=list, max_length=2)
    authoritative_failure_count: int | None = Field(default=None, ge=0, le=2)
    authoritative_external_evidence_count: int | None = Field(default=None, ge=0, le=4)
    authoritative_external_unique_evidence_count: int | None = Field(default=None, ge=0, le=4)
    authoritative_final_evidence_count: int | None = Field(default=None, ge=0, le=35)
    authoritative_status_before: EvidenceStatus | None = None
    authoritative_status_after: EvidenceStatus | None = None
    authoritative_scope_supported_before: bool | None = None
    authoritative_scope_supported_after: bool | None = None
    final_evidence_count: int | None = Field(default=None, ge=0, le=35)
    final_evidence_status: EvidenceStatus | None = None
    final_covered_domains: list[str] = Field(default_factory=list, max_length=6)
    final_missing_domains: list[str] = Field(default_factory=list, max_length=6)
    final_question_scope: str | None = Field(default=None, max_length=40)
    final_scope_supported: bool | None = None
    final_scope_support_reason: str | None = Field(default=None, max_length=1000)


class CopilotRequestStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    status: Literal["running", "completed", "failed", "cancelled"]
    current_stage: PipelineStage
    evidence_status: EvidenceStatus | None = None
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    failure_stage: PipelineStage | None = None
    failure_code: str | None = Field(default=None, max_length=80)
    stages: list[CopilotStageResponse] = Field(default_factory=list, max_length=11)
    diagnostics: CopilotDiagnosticsResponse | None = None


class TraceResourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: Literal["project", "document", "message", "conversation", "external"]
    resource_id: uuid.UUID | str
    version_id: uuid.UUID | None = None
    section: str | None = Field(default=None, max_length=200)
    page: int | None = Field(default=None, ge=1)
    locator: str | None = Field(default=None, max_length=500)


class AgentRunRequestTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1", max_length=40)
    intent: str | None = Field(default=None, max_length=120)
    locale: str | None = Field(default=None, max_length=20)
    experiment_id: str | None = Field(default=None, max_length=80)
    configuration_version: str | None = Field(default=None, max_length=120)
    context_refs: list[TraceResourceRef] = Field(default_factory=list, max_length=50)


class TraceSourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(max_length=255)
    knowledge_document_id: uuid.UUID | None = None
    chunk_id: str | None = Field(default=None, max_length=255)
    section: str | None = Field(default=None, max_length=200)
    page: int | None = Field(default=None, ge=1)
    locator: str | None = Field(default=None, max_length=500)


class AgentRunResponseTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1", max_length=40)
    summary: str | None = Field(default=None, max_length=2000)
    # Pipeline fallback and verification diagnostics add bounded scalar-only
    # fields to the existing allowlist; this remains a projection, not an
    # arbitrary application-object trace.
    result: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=110)
    source_refs: list[TraceSourceRef] = Field(default_factory=list, max_length=50)


class ModelTraceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=120)
    model_version: str | None = Field(default=None, max_length=120)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    max_output_tokens: int | None = Field(default=None, gt=0)
    response_format: str | None = Field(default=None, max_length=80)


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    parent_run_id: uuid.UUID | None
    user_id: uuid.UUID | None
    message_id: uuid.UUID | None
    agent_name: str
    capability: str
    status: str
    prompt_version: str | None
    started_at: datetime
    completed_at: datetime | None
