"""Gemini Interactions API adapter for the provider-neutral LLM contract."""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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


def _safe_identifier(value: Any, limit: int = 200) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"[^A-Za-z0-9._:/-]", "", value)[:limit]
    return cleaned or None


def _duration_seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)s\s*", value)
        if match:
            return float(match.group(1))
    return None


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    seconds = _duration_seconds(value)
    if seconds is not None:
        return seconds
    if value:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            pass
    return None


def _safe_error_metadata(response: httpx.Response) -> dict[str, Any]:
    """Extract only documented operational identifiers, never raw error text."""
    metadata: dict[str, Any] = {
        "provider_status": response.status_code,
        "provider_error_code": None,
        "provider_error_status": None,
        "retry_after_seconds": _retry_after_seconds(response),
        "quota_metric": None,
        "quota_id": None,
        "quota_location": None,
        "quota_model": None,
        "rate_limit_classification": "UNKNOWN",
    }
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        return metadata
    if not isinstance(payload, dict):
        return metadata
    error = payload.get("error")
    if not isinstance(error, dict):
        return metadata
    if isinstance(error.get("code"), int):
        metadata["provider_error_code"] = error["code"]
    metadata["provider_error_status"] = _safe_identifier(error.get("status"), 80)
    # The Interactions endpoint does not always return QuotaFailure details.
    # Inspect the provider message only to classify it; never return or log it.
    message = error.get("message")
    safe_message_classification = ""
    if isinstance(message, str):
        lowered_message = message.casefold()
        if any(marker in lowered_message for marker in ("per day", "per_day", "daily quota", "requests/day")):
            safe_message_classification = "DAILY_QUOTA"
        elif any(marker in lowered_message for marker in ("token rate", "tokens per minute", "tokens/min")):
            safe_message_classification = "TOKEN_RATE"
        elif any(marker in lowered_message for marker in ("model capacity", "overloaded", "resource exhausted")):
            safe_message_classification = "MODEL_CAPACITY"
        elif any(marker in lowered_message for marker in ("request rate", "requests per minute", "rate limit", "too many requests")):
            safe_message_classification = "REQUEST_RATE"
    for detail in error.get("details", []):
        if not isinstance(detail, dict):
            continue
        detail_type = str(detail.get("@type") or "")
        if detail_type.endswith("RetryInfo"):
            metadata["retry_after_seconds"] = _duration_seconds(detail.get("retryDelay")) or metadata["retry_after_seconds"]
        if not detail_type.endswith("QuotaFailure"):
            continue
        violations = detail.get("violations")
        if not isinstance(violations, list) or not violations:
            continue
        violation = violations[0] if isinstance(violations[0], dict) else {}
        metadata["quota_metric"] = _safe_identifier(violation.get("quotaMetric"))
        metadata["quota_id"] = _safe_identifier(violation.get("quotaId"))
        dimensions = violation.get("quotaDimensions")
        if isinstance(dimensions, dict):
            metadata["quota_location"] = _safe_identifier(dimensions.get("location"), 80)
            metadata["quota_model"] = _safe_identifier(dimensions.get("model"), 120)
    quota = f"{metadata['quota_metric'] or ''} {metadata['quota_id'] or ''}".casefold()
    if any(marker in quota for marker in ("perday", "per_day", "daily")):
        metadata["rate_limit_classification"] = "DAILY_QUOTA"
    elif "token" in quota:
        metadata["rate_limit_classification"] = "TOKEN_RATE"
    elif "request" in quota:
        metadata["rate_limit_classification"] = "REQUEST_RATE"
    elif safe_message_classification:
        metadata["rate_limit_classification"] = safe_message_classification
    return metadata


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
        max_attempts: int = 3,
        retry_base_seconds: float = 3.0,
        retry_max_seconds: float = 30.0,
        max_total_wait_seconds: float = 90.0,
        min_request_interval_seconds: float = 12.5,
    ) -> None:
        if not _secret_value(api_key):
            raise LLMConfigurationError("Gemini API key is not configured")
        if not model:
            raise LLMConfigurationError("gemini model is not configured")
        self.api_key = _secret_value(api_key)
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = client
        self.max_attempts = max(1, min(max_attempts, 5))
        self.retry_base_seconds = max(0.1, retry_base_seconds)
        self.retry_max_seconds = max(self.retry_base_seconds, retry_max_seconds)
        self.max_total_wait_seconds = max(1.0, max_total_wait_seconds)
        self.min_request_interval_seconds = max(0.0, min_request_interval_seconds)
        self._request_lock = asyncio.Lock()
        self._last_request_finished = 0.0

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
        response: httpx.Response | None = None
        body: dict[str, Any] = {}
        try:
            try:
                await asyncio.wait_for(self._request_lock.acquire(), timeout=self.max_total_wait_seconds)
            except TimeoutError as exc:
                self._raise_unavailable(request, started, 408, "provider queue wait exhausted", type(exc).__name__)
            try:
                attempt_limit = request.max_provider_attempts or self.max_attempts
                for attempt in range(1, attempt_limit + 1):
                    spacing = self.min_request_interval_seconds - (time.perf_counter() - self._last_request_finished)
                    remaining = self.max_total_wait_seconds - (time.perf_counter() - started)
                    if spacing > 0:
                        if spacing >= remaining:
                            self._raise_unavailable(request, started, 408, "provider pacing wait exhausted", "TimeoutError")
                        await asyncio.sleep(spacing)
                    remaining = max(1.0, self.max_total_wait_seconds - (time.perf_counter() - started))
                    try:
                        response = await client.post(
                            f"{self.base_url}/interactions",
                            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                            json=payload,
                            timeout=min(120.0, remaining),
                        )
                    except (httpx.TimeoutException, httpx.TransportError) as exc:
                        self._last_request_finished = time.perf_counter()
                        if attempt >= attempt_limit:
                            self._raise_unavailable(request, started, 408 if isinstance(exc, httpx.TimeoutException) else None, str(exc), type(exc).__name__)
                        await self._retry_wait(request, started, attempt, None, "TRANSIENT_TRANSPORT")
                        continue
                    self._last_request_finished = time.perf_counter()
                    if response.status_code < 400:
                        break
                    metadata = _safe_error_metadata(response)
                    retryable = response.status_code in {429, 500, 502, 503, 504}
                    hard_quota = metadata["rate_limit_classification"] == "DAILY_QUOTA"
                    if not retryable or hard_quota or attempt >= attempt_limit:
                        self._raise_unavailable(request, started, response.status_code, self._safe_failure_reason(metadata), "HTTPStatusError", metadata)
                    await self._retry_wait(
                        request,
                        started,
                        attempt,
                        metadata.get("retry_after_seconds"),
                        metadata["rate_limit_classification"] if response.status_code == 429 else "UPSTREAM_5XX",
                        metadata,
                    )
                if response is None:
                    self._raise_unavailable(request, started, None, "provider returned no response", "RuntimeError")
            finally:
                self._request_lock.release()
            duration_ms = (time.perf_counter() - started) * 1000
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
                retry_count=attempt - 1,
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
            exc.http_status = response.status_code if response is not None else None
            exc.cause_type = type(exc).__name__
            exc.usage = _usage(body)
            dependency_result(dependency=self.provider_name, operation=request.operation, status='error', duration_ms=exc.duration_ms, error_category=exc.category)
            raise
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

    async def _retry_wait(self, request: LLMGenerationRequest, started: float, attempt: int, retry_after: float | None, reason: str, metadata: dict[str, Any] | None = None) -> None:
        exponential = min(self.retry_max_seconds, self.retry_base_seconds * (2 ** (attempt - 1)))
        # When Gemini omits Retry-After and quota details, a short 3/6-second
        # retry sequence only repeats the observed rolling-window failure.
        # Use the configured bounded ceiling as a conservative cooldown.
        if reason == "UNKNOWN":
            exponential = self.retry_max_seconds
        delay = max(retry_after or 0.0, exponential) + random.uniform(0, min(0.5, exponential * 0.15))
        remaining = self.max_total_wait_seconds - (time.perf_counter() - started)
        if delay >= remaining:
            self._raise_unavailable(request, started, 429 if reason in {"REQUEST_RATE", "TOKEN_RATE", "UNKNOWN"} else 503, f"{reason}; bounded retry wait exhausted", "RetryBudgetExhausted", metadata)
        emit_event(
            "llm.provider.retry_scheduled",
            component="llm",
            operation=request.operation,
            status="retrying",
            provider=self.provider_name,
            model=self.model,
            retry_count=attempt,
            retry_delay_ms=round(delay * 1000, 3),
            error_category=reason,
            provider_status=(metadata or {}).get("provider_status"),
            provider_error_code=(metadata or {}).get("provider_error_code"),
            provider_error_status=(metadata or {}).get("provider_error_status"),
            retry_after_seconds=(metadata or {}).get("retry_after_seconds"),
            quota_metric=(metadata or {}).get("quota_metric"),
            quota_id=(metadata or {}).get("quota_id"),
            quota_location=(metadata or {}).get("quota_location"),
            quota_model=(metadata or {}).get("quota_model"),
        )
        await asyncio.sleep(delay)

    @staticmethod
    def _safe_failure_reason(metadata: dict[str, Any]) -> str:
        values = [
            metadata.get("provider_error_status"),
            metadata.get("rate_limit_classification"),
            metadata.get("quota_metric"),
            metadata.get("quota_id"),
            metadata.get("quota_location"),
            metadata.get("quota_model"),
        ]
        return ";".join(str(value) for value in values if value) or f"HTTP {metadata.get('provider_status')}"

    def _raise_unavailable(self, request: LLMGenerationRequest, started: float, status_code: int | None, message: str, cause_type: str, metadata: dict[str, Any] | None = None) -> None:
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
        if metadata:
            error.retry_after_seconds = metadata.get("retry_after_seconds")
            error.quota_metric = metadata.get("quota_metric")
            error.quota_location = metadata.get("quota_location")
            error.quota_model = metadata.get("quota_model")
            error.rate_limit_classification = metadata.get("rate_limit_classification")
        raise error
