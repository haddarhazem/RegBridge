"""Provider-neutral contracts for bounded language-model generation."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class LLMMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class LLMGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[LLMMessage] = Field(min_length=1, max_length=20)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=900, gt=0, le=4000)
    response_format: dict[str, Any] | None = None
    prompt_version: str | None = Field(default=None, max_length=80)
    operation: str | None = Field(default=None, max_length=100)


class LLMExecutionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str | None = Field(default=None, max_length=80)
    logical_model: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    prompt_version: str | None = Field(default=None, max_length=80)
    operation: str | None = Field(default=None, max_length=100)
    status: Literal["success", "failed"]
    duration_ms: float | None = Field(default=None, ge=0)
    error_category: str | None = Field(default=None, max_length=80)
    prompt_tokens: int | float | None = Field(default=None, ge=0)
    completion_tokens: int | float | None = Field(default=None, ge=0)
    total_tokens: int | float | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)


class LLMGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=30000)
    model: str = Field(min_length=1, max_length=200)
    finish_reason: str | None = Field(default=None, max_length=80)
    usage: dict[str, int | float] = Field(default_factory=dict, max_length=20)
    execution: LLMExecutionMetadata | None = None


class LLMProviderError(RuntimeError):
    """Base class for controlled provider failures."""

    def __init__(self, message: str, *, category: str = "provider_error") -> None:
        super().__init__(message)
        self.category = category
        self.duration_ms: float | None = None
        self.provider: str | None = None
        self.model: str | None = None
        self.prompt_version: str | None = None
        self.operation: str | None = None
        self.cause_type: str | None = None
        self.cause_message: str | None = None
        self.http_status: int | None = None


class LLMConfigurationError(LLMProviderError):
    """Provider configuration is missing or invalid."""


class LLMProviderUnavailableError(LLMProviderError):
    """The configured provider cannot currently be reached."""


class LLMGenerationError(LLMProviderError):
    """The provider returned an unusable generation result."""


class LLMProvider(Protocol):
    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        """Generate text using a provider-neutral request."""
