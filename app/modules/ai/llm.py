"""Provider-neutral contracts for bounded language-model generation."""

from __future__ import annotations

from typing import Literal, Protocol

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


class LLMGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=30000)
    model: str = Field(min_length=1, max_length=200)
    finish_reason: str | None = Field(default=None, max_length=80)
    usage: dict[str, int | float] = Field(default_factory=dict, max_length=20)


class LLMProviderError(RuntimeError):
    """Base class for controlled provider failures."""


class LLMConfigurationError(LLMProviderError):
    """Provider configuration is missing or invalid."""


class LLMProviderUnavailableError(LLMProviderError):
    """The configured provider cannot currently be reached."""


class LLMGenerationError(LLMProviderError):
    """The provider returned an unusable generation result."""


class LLMProvider(Protocol):
    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        """Generate text using a provider-neutral request."""
