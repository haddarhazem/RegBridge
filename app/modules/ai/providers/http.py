"""HTTP adapters for provider-neutral DeepSeek and Ollama generation."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from pydantic import SecretStr

from app.core.observability import dependency_result, elapsed_ms, emit_event
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
    if status_code == 429:
        return "provider_rate_limited"
    if status_code == 402:
        return "provider_payment_required"
    if status_code in {401, 403}:
        return "provider_authentication_failed"
    return "provider_unavailable"


def _schema_instruction(schema: dict[str, Any]) -> dict[str, str]:
    return {
        "role": "system",
        "content": "Return only one JSON object matching this exact schema. Do not add fields or prose: "
        + json.dumps(schema, ensure_ascii=True, separators=(",", ":")),
    }


class _HTTPProvider:
    provider_name: str

    def __init__(self, *, api_key: SecretStr | str | None, model: str, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        if not model:
            raise LLMConfigurationError(f"{self.provider_name} model is not configured")
        self.api_key = _secret_value(api_key)
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = client

    async def _post(self, path: str, payload: dict[str, Any], request: LLMGenerationRequest) -> tuple[dict[str, Any], float]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        started = time.perf_counter()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=120)
        try:
            response = await client.post(f"{self.base_url}{path}", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("Provider returned a non-object response")
            return body, (time.perf_counter() - started) * 1000
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            self._raise_unavailable(request, started, status_code, f"HTTP {status_code}", type(exc).__name__)
        except (httpx.HTTPError, ValueError) as exc:
            self._raise_unavailable(request, started, None, str(exc), type(exc).__name__)
        finally:
            if owns_client:
                await client.aclose()
        raise AssertionError("unreachable")

    def _raise_unavailable(self, request: LLMGenerationRequest, started: float, status_code: int | None, message: str, cause_type: str) -> None:
        duration_ms = (time.perf_counter() - started) * 1000
        category = _error_category(status_code)
        dependency_result(dependency=self.provider_name, operation=request.operation, status="error", duration_ms=duration_ms, error_category=category)
        error = LLMProviderUnavailableError(f"{self.provider_name} generation service is unavailable", category=category)
        error.duration_ms = duration_ms
        error.provider = self.provider_name
        error.model = self.model
        error.prompt_version = request.prompt_version
        error.operation = request.operation
        error.cause_type = cause_type
        error.cause_message = _safe_message(message)
        error.http_status = status_code
        raise error

    def _response(self, *, content: Any, returned_model: Any, finish_reason: Any, usage: dict[str, int | float], duration_ms: float, request: LLMGenerationRequest) -> LLMGenerationResponse:
        if not isinstance(content, str) or not content.strip():
            raise LLMGenerationError(f"{self.provider_name} returned an invalid response", category="provider_generation_error")
        model = str(returned_model or self.model)
        dependency_result(dependency=self.provider_name, operation=request.operation, status="ok", duration_ms=duration_ms)
        emit_event("llm.generation.completed", component="llm", operation=request.operation, status="ok", provider=self.provider_name, model=model, prompt_version=request.prompt_version, retry_count=0, prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"), total_tokens=usage.get("total_tokens"))
        execution = LLMExecutionMetadata(provider=self.provider_name, logical_model=self.model, model=model, prompt_version=request.prompt_version, operation=request.operation, status="success", duration_ms=duration_ms, prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"), total_tokens=usage.get("total_tokens"), estimated_cost=None)
        return LLMGenerationResponse(content=content.strip(), model=model, finish_reason=str(finish_reason) if finish_reason else None, usage=usage, execution=execution)


class DeepSeekLLMProvider(_HTTPProvider):
    provider_name = "deepseek"

    def __init__(self, *, api_key: SecretStr | str | None, model: str, base_url: str = "https://api.deepseek.com", client: httpx.AsyncClient | None = None) -> None:
        if not _secret_value(api_key):
            raise LLMConfigurationError("DeepSeek API key is not configured")
        super().__init__(api_key=api_key, model=model, base_url=base_url, client=client)

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        messages = [item.model_dump() for item in request.messages]
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": request.temperature, "max_tokens": request.max_tokens, "stream": False}
        if request.response_format is not None:
            if request.response_format.get("type") == "json_schema":
                schema = request.response_format.get("json_schema", {}).get("schema")
                payload["response_format"] = {"type": "json_object"}
                if isinstance(schema, dict):
                    messages.insert(0, _schema_instruction(schema))
            else:
                payload["response_format"] = request.response_format
        body, duration_ms = await self._post("/chat/completions", payload, request)
        try:
            choice = body["choices"][0]
            usage_source = body.get("usage") or {}
            usage = {key: value for key in ("prompt_tokens", "completion_tokens", "total_tokens") if isinstance((value := usage_source.get(key)), (int, float))}
            return self._response(content=choice["message"]["content"], returned_model=body.get("model"), finish_reason=choice.get("finish_reason"), usage=usage, duration_ms=duration_ms, request=request)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMGenerationError("DeepSeek returned an invalid response", category="provider_generation_error") from exc


class OllamaLLMProvider(_HTTPProvider):
    provider_name = "ollama"

    def __init__(self, *, api_key: SecretStr | str | None, model: str, base_url: str = "https://ollama.com/api", client: httpx.AsyncClient | None = None) -> None:
        is_local = base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1")
        if not is_local and not _secret_value(api_key):
            raise LLMConfigurationError("Ollama API key is not configured for cloud access")
        super().__init__(api_key=api_key, model=model, base_url=base_url, client=client)

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        messages = [item.model_dump() for item in request.messages]
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False, "think": False, "options": {"temperature": request.temperature, "num_predict": request.max_tokens}}
        if request.response_format is not None:
            if request.response_format.get("type") == "json_schema":
                schema = request.response_format.get("json_schema", {}).get("schema", "json")
                payload["format"] = schema
                if isinstance(schema, dict):
                    messages.insert(0, _schema_instruction(schema))
            else:
                payload["format"] = "json"
        body, duration_ms = await self._post("/chat", payload, request)
        try:
            prompt_tokens = body.get("prompt_eval_count")
            completion_tokens = body.get("eval_count")
            usage: dict[str, int | float] = {}
            if isinstance(prompt_tokens, (int, float)):
                usage["prompt_tokens"] = prompt_tokens
            if isinstance(completion_tokens, (int, float)):
                usage["completion_tokens"] = completion_tokens
            if usage:
                usage["total_tokens"] = sum(usage.values())
            return self._response(content=body["message"]["content"], returned_model=body.get("model"), finish_reason=body.get("done_reason"), usage=usage, duration_ms=duration_ms, request=request)
        except (KeyError, TypeError) as exc:
            raise LLMGenerationError("Ollama returned an invalid response", category="provider_generation_error") from exc
