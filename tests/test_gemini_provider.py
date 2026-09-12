import json

import httpx
import pytest
from pydantic import SecretStr

from app.modules.ai.llm import LLMGenerationError, LLMGenerationRequest, LLMMessage, LLMProviderUnavailableError
from app.modules.ai.providers.gemini import GeminiLLMProvider, _schema_payload


def _request(**kwargs):
    return LLMGenerationRequest(messages=[LLMMessage(role="system", content="Be concise"), LLMMessage(role="user", content="Return JSON")], **kwargs)


def test_gemini_schema_hint_flattens_pydantic_refs_without_changing_local_validation() -> None:
    schema = {
        "type": "object",
        "$defs": {"Claim": {"type": "object", "properties": {"support": {"type": "string", "enum": ["supported"]}}, "required": ["support"]}},
        "properties": {"claims": {"type": "array", "items": {"$ref": "#/$defs/Claim"}}},
    }

    payload = _schema_payload({"type": "json_schema", "json_schema": {"schema": schema}})

    assert "$defs" not in json.dumps(payload)
    assert payload["schema"]["properties"]["claims"]["items"]["properties"]["support"]["enum"] == ["supported"]


@pytest.mark.asyncio
async def test_gemini_maps_interactions_response_and_usage() -> None:
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.headers["x-goog-api-key"] == "test-secret"
        return httpx.Response(200, json={"model": "gemini-test", "status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": "Bonjour"}]}], "usage": {"total_input_tokens": 4, "total_output_tokens": 2, "total_tokens": 6}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiLLMProvider(api_key=SecretStr("test-secret"), model="gemini-3.8-flash", client=client)
        result = await provider.generate(_request(max_tokens=32))

    assert captured["model"] == "gemini-3.8-flash"
    assert captured["store"] is False
    assert captured["system_instruction"] == "Be concise"
    assert result.content == "Bonjour"
    assert result.execution is not None and result.execution.provider == "gemini"
    assert result.usage == {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}
    assert "test-secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_gemini_maps_json_schema_to_interactions_response_format() -> None:
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"model": "gemini-test", "status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": '{"status":"ok"}'}]}]})

    schema = {"type": "json_schema", "json_schema": {"name": "Result", "schema": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]}}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiLLMProvider(api_key=SecretStr("test-secret"), model="gemini-3.8-flash", client=client)
        await provider.generate(_request(response_format=schema))

    assert captured["response_format"] == {"type": "text", "mime_type": "application/json", "schema": schema["json_schema"]["schema"]}


@pytest.mark.asyncio
async def test_gemini_maps_rate_limit_without_leaking_secret() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "test-secret"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiLLMProvider(api_key=SecretStr("test-secret"), model="gemini-3.8-flash", client=client)
        with pytest.raises(LLMProviderUnavailableError) as caught:
            await provider.generate(_request())

    assert caught.value.category == "provider_rate_limited"
    assert caught.value.http_status == 429
    assert "test-secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_gemini_empty_generation_fails_closed() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "gemini-test", "status": "completed", "steps": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiLLMProvider(api_key=SecretStr("test-secret"), model="gemini-3.8-flash", client=client)
        with pytest.raises(LLMGenerationError) as caught:
            await provider.generate(_request())

    assert caught.value.category == "provider_empty_generation"
    assert caught.value.http_status == 200
    assert caught.value.provider == 'gemini'


@pytest.mark.asyncio
async def test_incomplete_gemini_output_is_rejected_with_safe_usage():
    async def handler(_request):
        return httpx.Response(200, json={'status': 'incomplete', 'steps': [{'type': 'model_output', 'content': [{'type': 'text', 'text': 'SECRET_PARTIAL_DO_NOT_PUBLISH'}]}], 'usage': {'total_output_tokens': 900}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiLLMProvider(api_key=SecretStr('test-secret'), model='gemini-3.8-flash', client=client)
        with pytest.raises(LLMGenerationError) as caught:
            await provider.generate(_request())
    assert caught.value.category == 'provider_incomplete_generation'
    assert caught.value.usage == {'completion_tokens': 900}
    assert 'SECRET_PARTIAL' not in str(caught.value)
    assert caught.value.http_status == 200
