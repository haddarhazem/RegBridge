"""Mistral adapter for the provider-neutral LLM contract."""

from __future__ import annotations

from functools import lru_cache
import time
from typing import Any

from mistralai.client import Mistral
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.modules.ai.llm import (
    LLMConfigurationError,
    LLMGenerationError,
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMExecutionMetadata,
    LLMProviderUnavailableError,
)


class MistralLLMProvider:
    """Translate the provider-neutral contract to the official Mistral SDK."""

    def __init__(self, *, api_key: SecretStr | str | None, model: str | None, client: Any | None = None) -> None:
        if api_key is None or (api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key) == "":
            raise LLMConfigurationError("Mistral API key is not configured")
        if not model:
            raise LLMConfigurationError("Mistral model is not configured")
        self.model = model
        self._client = client or Mistral(api_key=api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key)

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        messages = [message.model_dump() for message in request.messages]
        started = time.perf_counter()
        try:
            response = await self._client.chat.complete_async(
                model=self.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response_format=request.response_format,
            )
        except Exception as exc:
            error = LLMProviderUnavailableError("Mistral generation service is unavailable", category="provider_unavailable")
            error.duration_ms = (time.perf_counter() - started) * 1000
            error.provider = "mistral"
            error.model = self.model
            error.prompt_version = request.prompt_version
            error.operation = request.operation
            error.cause_type = type(exc).__name__
            error.cause_message = _safe_provider_message(exc)
            error.http_status = getattr(exc, "status_code", None) if isinstance(getattr(exc, "status_code", None), int) else None
            raise error from exc

        try:
            choice = response.choices[0]
            content = choice.message.content
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Mistral returned an empty response")
        except LLMGenerationError:
            raise
        except Exception as exc:
            error = LLMGenerationError("Mistral returned an invalid response", category="provider_generation_error")
            error.duration_ms = (time.perf_counter() - started) * 1000
            error.provider = "mistral"
            error.model = self.model
            error.prompt_version = request.prompt_version
            error.operation = request.operation
            error.cause_type = type(exc).__name__
            error.cause_message = _safe_provider_message(exc)
            raise error from exc

        duration_ms = (time.perf_counter() - started) * 1000
        usage = _safe_usage(getattr(response, "usage", None))
        execution = LLMExecutionMetadata(
            provider="mistral",
            logical_model=self.model,
            model=str(getattr(response, "model", self.model)),
            prompt_version=request.prompt_version,
            operation=request.operation,
            status="success",
            duration_ms=duration_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            estimated_cost=None,
        )
        return LLMGenerationResponse(
            content=content.strip(),
            model=str(getattr(response, "model", self.model)),
            finish_reason=getattr(choice, "finish_reason", None),
            usage=usage,
            execution=execution,
        )


def _safe_usage(usage: Any) -> dict[str, int | float]:
    if usage is None:
        return {}
    result: dict[str, int | float] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, key, None)
        if isinstance(value, (int, float)):
            result[key] = value
    return result


def _safe_provider_message(exc: Exception) -> str:
    """Keep bounded diagnostics without credentials, headers, or request data."""
    message = str(exc)
    for marker in ("authorization", "api-key", "api_key", "bearer"):
        if marker.casefold() in message.casefold():
            return "provider exception contained sensitive authentication data"
    return message[:500]


@lru_cache(maxsize=1)
def get_mistral_provider() -> MistralLLMProvider:
    settings: Settings = get_settings()
    return MistralLLMProvider(api_key=settings.mistral_api_key, model=settings.mistral_model)
