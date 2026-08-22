"""Provider-neutral production contracts for AI orchestration."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.identity.schemas import AuthenticatedPrincipal


class OrchestrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    question: str = Field(default="", max_length=4000)
    principal: AuthenticatedPrincipal | None = None
    subject_type: Literal["project"] | None = None
    subject_id: uuid.UUID | None = None
    intent_hint: str | list[str] = Field(min_length=1)
    locale: str = Field(default="en", max_length=20)

    @model_validator(mode="after")
    def validate_subject(self) -> "OrchestrationRequest":
        if (self.subject_type is None) != (self.subject_id is None):
            raise ValueError("subject_type and subject_id must be provided together")
        return self


class IntentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: list[str] = Field(default_factory=list, max_length=10)
    classifier_version: str = Field(default="deterministic-v1", max_length=80)


class AuthorizedContext(BaseModel):
    """Minimal authorized projection; no ORM, session, token, or repository."""

    model_config = ConfigDict(extra="forbid")

    subject_type: Literal["project"] | None = None
    subject_id: uuid.UUID | None = None
    project_type: str | None = Field(default=None, max_length=40)
    country_code: str | None = Field(default=None, max_length=2)
    user_goal: str | None = Field(default=None, max_length=2000)


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    parent_run_id: uuid.UUID
    question: str = Field(default="", max_length=4000)
    capability: str = Field(max_length=100)
    locale: str = Field(max_length=20)
    subject_type: Literal["project"] | None = None
    subject_id: uuid.UUID | None = None
    authorized_context: AuthorizedContext


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(max_length=80)
    capability: str = Field(max_length=100)
    status: Literal["succeeded", "failed"]
    answer: str | None = Field(default=None, max_length=30000)
    findings: list[str] = Field(default_factory=list, max_length=50)
    risks: list[str] = Field(default_factory=list, max_length=50)
    recommendations: list[str] = Field(default_factory=list, max_length=50)
    missing_information: list[str] = Field(default_factory=list, max_length=50)
    sources: list[str] = Field(default_factory=list, max_length=50)
    confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list, max_length=50)
    artifacts: list[str] = Field(default_factory=list, max_length=50)
    structured_payload: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=50)
    evidence: list[dict[str, str | int | float | None]] = Field(default_factory=list, max_length=5)
    run_id: uuid.UUID | None = None
    error_code: str | None = Field(default=None, max_length=80)


class OrchestrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    status: Literal["succeeded", "partial", "failed", "unauthorized", "unsupported"]
    selected_capabilities: list[str] = Field(default_factory=list, max_length=10)
    results: list[AgentResult] = Field(default_factory=list, max_length=20)
    failures: list[AgentResult] = Field(default_factory=list, max_length=20)
    provenance: list[str] = Field(default_factory=list, max_length=50)
    warnings: list[str] = Field(default_factory=list, max_length=50)
