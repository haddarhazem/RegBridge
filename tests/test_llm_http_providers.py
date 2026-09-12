import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.modules.ai.llm import LLMGenerationRequest, LLMMessage, LLMProviderUnavailableError
from app.modules.ai.providers.http import DeepSeekLLMProvider, OllamaLLMProvider
from app.modules.ai.providers import selection


@pytest.mark.asyncio
async def test_deepseek_maps_provider_neutral_chat_and_usage() -> None:
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"model": "deepseek-v4-flash", "choices": [{"message": {"content": "Bonjour"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = DeepSeekLLMProvider(api_key=SecretStr("test-secret"), model="deepseek-v4-flash", client=client)
        result = await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content="Bonjour")], max_tokens=32))

    assert captured["model"] == "deepseek-v4-flash"
    assert captured["messages"] == [{"role": "user", "content": "Bonjour"}]
    assert result.execution is not None and result.execution.provider == "deepseek"
    assert result.usage["total_tokens"] == 6


@pytest.mark.asyncio
async def test_deepseek_translates_json_schema_to_supported_json_object_mode() -> None:
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"model": "deepseek-v4-flash", "choices": [{"message": {"content": '{"status":"ok"}'}, "finish_reason": "stop"}]})

    schema = {"type": "json_schema", "json_schema": {"name": "Result", "schema": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]}}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = DeepSeekLLMProvider(api_key=SecretStr("test-secret"), model="deepseek-v4-flash", client=client)
        await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content="Return JSON")], response_format=schema))

    assert captured["response_format"] == {"type": "json_object"}
    assert captured["messages"][0]["role"] == "system"
    assert "exact schema" in captured["messages"][0]["content"]


@pytest.mark.asyncio
async def test_ollama_maps_json_schema_and_native_usage() -> None:
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"model": "gpt-oss:20b", "message": {"role": "assistant", "content": '{"status":"ok"}'}, "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 4})

    schema = {"type": "json_schema", "json_schema": {"name": "Result", "schema": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]}}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaLLMProvider(api_key=SecretStr("test-secret"), model="gpt-oss:20b", client=client)
        result = await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content="Return JSON")], max_tokens=32, response_format=schema))

    assert captured["format"] == schema["json_schema"]["schema"]
    assert captured["think"] is False
    assert captured["messages"][0]["role"] == "system"
    assert "exact schema" in captured["messages"][0]["content"]
    assert captured["options"]["num_predict"] == 32
    assert result.execution is not None and result.execution.provider == "ollama"
    assert result.usage == {"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9}


@pytest.mark.asyncio
async def test_http_provider_preserves_payment_required_without_secret() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": "test-secret"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = DeepSeekLLMProvider(api_key=SecretStr("test-secret"), model="deepseek-v4-flash", client=client)
        with pytest.raises(LLMProviderUnavailableError) as caught:
            await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content="Bonjour")]))

    assert caught.value.category == "provider_payment_required"
    assert caught.value.http_status == 402
    assert "test-secret" not in str(caught.value)


def test_configured_provider_selection_is_explicit(monkeypatch) -> None:
    settings = SimpleNamespace(
        llm_provider="ollama",
        ollama_api_key=SecretStr("test-secret"),
        ollama_model="gpt-oss:20b",
        ollama_base_url="https://ollama.com/api",
    )
    monkeypatch.setattr(selection, "get_settings", lambda: settings)
    selection.get_llm_provider.cache_clear()
    try:
        provider = selection.get_llm_provider()
        assert isinstance(provider, OllamaLLMProvider)
        assert provider.model == "gpt-oss:20b"
    finally:
        selection.get_llm_provider.cache_clear()
