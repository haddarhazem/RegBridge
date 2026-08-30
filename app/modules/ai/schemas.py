import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    result: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=50)
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
