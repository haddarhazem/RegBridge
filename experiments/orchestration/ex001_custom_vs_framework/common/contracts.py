from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    user_id: uuid.UUID
    resource_id: uuid.UUID
    scenario_id: str = Field(pattern=r"^S[1-6]$", max_length=10)
    declared_intent: str = Field(max_length=80)
    locale: str = Field(default="en", max_length=20)


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: list[str] = Field(max_length=10)


class AuthorizedContext(BaseModel):
    """Minimal projection; resource bodies never enter a trace payload."""

    model_config = ConfigDict(extra="forbid")

    resource_id: uuid.UUID
    project_name: str = Field(max_length=255)
    authorized_summary: str = Field(max_length=500)


class AgentExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    parent_run_id: uuid.UUID
    intent: str = Field(max_length=80)
    authorized_context: AuthorizedContext
    locale: str = Field(max_length=20)


class AgentExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(max_length=80)
    capability: str = Field(max_length=80)
    status: Literal["succeeded", "failed"]
    findings: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    sources: list[str] = Field(default_factory=list, max_length=20)
    structured_payload: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=20)
    error_code: str | None = Field(default=None, max_length=80)


class OrchestrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    status: Literal["succeeded", "partial", "failed", "unauthorized", "unsupported"]
    results: list[AgentExecutionResult] = Field(default_factory=list, max_length=20)
    failures: list[str] = Field(default_factory=list, max_length=20)
    provenance: list[str] = Field(default_factory=list, max_length=50)


class TraceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    request_id: uuid.UUID
    parent_run_id: uuid.UUID | None
    agent_name: str
    capability: str
    status: Literal["queued", "running", "succeeded", "failed"]
    request_payload: dict
    response_payload: dict | None = None
    error_code: str | None = None

