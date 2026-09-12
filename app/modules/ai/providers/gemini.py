"""Gemini Interactions API adapter for the provider-neutral LLM contract."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from pydantic import SecretStr

from app.core.observability import dependency_result, emit_event
from app.modules.ai.llm import (
    LLMConfigurationError,
    LLMGenerationError,
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMExecutionMetadata,
    LLMProviderUnavailableError,
)


def _secret_value(value: SecretStr | str | None) -> str | None:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return value


def _safe_message(value: str) -> str:
    lowered = value.casefold()
    if any(marker in lowered for marker in ("authorization", "api-key", "api_key", "bearer")):
        return "provider exception contained sensitive authentication data"
    return value[:500]


def _error_category(status_code: int | None) -> str:
    if status_code == 408:
        return "provider_timeout"
    if status_code == 429:
        return "provider_rate_limited"
    if status_code in {401, 403}:
        return "provider_authentication_failed"
    if status_code == 400:
        return "provider_request_invalid"
    if status_code is not None and status_code >= 500:
        return "provider_unavailable"
    return "provider_error"


def _schema_payload(response_format: dict[str, Any]) -> dict[str, Any]:
    if response_format.get("type") == "json_schema":
        schema = response_format.get("json_schema", {}).get("schema")
        if not isinstance(schema, dict):
            raise LLMGenerationError("Gemini structured schema is invalid", category="invalid_structured_request")
        return {"type": "text", "mime_type": "application/json", "schema": _gemini_schema(schema)}
    return {"type": "text", "mime_type": "application/json"}


def _gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert Pydantic's schema dialect to Gemini's supported JSON subset.

    Pydantic's `$defs`/`$ref`, bounds, titles and additional-property controls
    are enforced again by the existing local Pydantic validator after the
    provider response returns. They are omitted only from the provider hint.
    """

    definitions = schema.get("$defs", {})

    def resolve(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {"type": "object"}
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            definition = definitions.get(reference.removeprefix("#/$defs/"))
            return resolve(definition)
        result: dict[str, Any] = {}
        schema_type = value.get("type")
        if isinstance(schema_type, (str, list)):
            result["type"] = schema_type
        if isinstance(value.get("enum"), list):
            result["enum"] = value["enum"]
        if schema_type == "object":
            result["properties"] = {key: resolve(item) for key, item in (value.get("properties") or {}).items()}
            if isinstance(value.get("required"), list):
                result["required"] = value["required"]
        elif schema_type == "array":
            result["items"] = resolve(value.get("items", {"type": "string"}))
        return result or {"type": "string"}

    return resolve(schema)


def _input_text(messages: list[Any]) -> tuple[str | None, str]:
    system_parts: list[str] = []
    input_parts: list[str] = []
    for message in messages:
        if message.role == "system":
            system_parts.append(message.content)
        else:
            input_parts.append(f"{message.role.upper()} MESSAGE\n{message.content}")
    return ("\n\n".join(system_parts) or None, "\n\n".join(input_parts))


def _usage(body: dict[str, Any]) -> dict[str, int | float]:
    source = body.get("usage")
    if not isinstance(source, dict):
        return {}
    mapping = {
        "total_input_tokens": "prompt_tokens",
        "total_output_tokens": "completion_tokens",
        "total_thought_tokens": "reasoning_tokens",
        "total_tokens": "total_tokens",
    }
    return {
        target: value
        for source_key, target in mapping.items()
        if isinstance((value := source.get(source_key)), (int, float))
    }


class GeminiLLMProvider:
    """Use Gemini's current Interactions API without storing interaction state."""

    provider_name = "gemini"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None,
        model: str,
        base_url: str = default_base_url,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not _secret_value(api_key):
            raise LLMConfigurationError("Gemini API key is not configured")
        if not model:
            raise LLMConfigurationError("gemini model is not configured")
        self.api_key = _secret_value(api_key)
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = client

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        system_instruction, input_text = _input_text(request.messages)
        if not input_text:
            raise LLMGenerationError("Gemini requires a user input", category="invalid_provider_request")
        generation_config: dict[str, Any] = {"max_output_tokens": request.max_tokens}
        if self.model.startswith("gemini-3.8"):
            generation_config["thinking_level"] = "low"
        else:
            generation_config["temperature"] = request.temperature
        payload: dict[str, Any] = {
            "model": self.model,
            "input": input_text,
            "store": False,
            "generation_config": generation_config,
        }
        if system_instruction:
            payload["system_instruction"] = system_instruction
        if request.response_format is not None:
            payload["response_format"] = _schema_payload(request.response_format)

        started = time.perf_counter()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=120)
        try:
            response = await client.post(
                f"{self.base_url}/interactions",
                headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                json=payload,
            )
            duration_ms = (time.perf_counter() - started) * 1000
            if response.status_code >= 400:
                self._raise_unavailable(request, started, response.status_code, f"HTTP {response.status_code}", "HTTPStatusError")
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("Gemini returned a non-object response")
            if body.get("status") not in {None, "completed"}:
                raise LLMGenerationError("Gemini interaction did not complete", category="provider_incomplete_generation")
            content = self._extract_text(body)
            usage = _usage(body)
            returned_model = str(body.get("model") or self.model)
            dependency_result(dependency=self.provider_name, operation=request.operation, status="ok", duration_ms=duration_ms)
            emit_event(
                "llm.generation.completed",
                component="llm",
                operation=request.operation,
                status="ok",
                provider=self.provider_name,
                model=returned_model,
                prompt_version=request.prompt_version,
                retry_count=0,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
            )
            execution = LLMExecutionMetadata(
                provider=self.provider_name,
                logical_model=self.model,
                model=returned_model,
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
                content=content,
                model=returned_model,
                finish_reason=body.get("status"),
                usage=usage,
                execution=execution,
            )
        except LLMGenerationError as exc:
            # Preserve safe diagnostics for a 200 response with no usable output.
            # Never attach the response body, generated content, or request headers.
            exc.duration_ms = (time.perf_counter() - started) * 1000
            exc.provider = self.provider_name
            exc.model = self.model
            exc.prompt_version = request.prompt_version
            exc.http_status = response.status_code
            exc.cause_type = type(exc).__name__
            exc.usage = _usage(body)
            dependency_result(dependency=self.provider_name, operation=request.operation, status='error', duration_ms=exc.duration_ms, error_category=exc.category)
            raise
        except httpx.TimeoutException as exc:
            self._raise_unavailable(request, started, 408, str(exc), type(exc).__name__)
        except httpx.HTTPError as exc:
            self._raise_unavailable(request, started, None, str(exc), type(exc).__name__)
        except (ValueError, json.JSONDecodeError) as exc:
            self._raise_unavailable(request, started, None, str(exc), type(exc).__name__)
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _extract_text(body: dict[str, Any]) -> str:
        steps = body.get("steps")
        if not isinstance(steps, list):
            raise LLMGenerationError("Gemini returned no interaction steps", category="provider_output_shape_invalid")
        for step in reversed(steps):
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            content = step.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str) and part["text"].strip():
                    return part["text"].strip()
        raise LLMGenerationError("Gemini returned an empty generation", category="provider_empty_generation")

    def _raise_unavailable(self, request: LLMGenerationRequest, started: float, status_code: int | None, message: str, cause_type: str) -> None:
        duration_ms = (time.perf_counter() - started) * 1000
        category = _error_category(status_code)
        dependency_result(dependency=self.provider_name, operation=request.operation, status="error", duration_ms=duration_ms, error_category=category)
        error = LLMProviderUnavailableError("Gemini generation service is unavailable", category=category)
        error.duration_ms = duration_ms
        error.provider = self.provider_name
        error.model = self.model
        error.prompt_version = request.prompt_version
        error.operation = request.operation
        error.cause_type = cause_type
        error.cause_message = _safe_message(message)
        error.http_status = status_code
        raise error
