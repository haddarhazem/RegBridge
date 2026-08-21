from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.modules.ai.llm import LLMConfigurationError, LLMGenerationRequest, LLMMessage, LLMProviderUnavailableError
from app.modules.ai.providers.mistral import MistralLLMProvider


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.chat = self

    async def complete_async(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def response():
    return SimpleNamespace(
        model="mistral-test",
        choices=[SimpleNamespace(message=SimpleNamespace(content="Réponse sûre"), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


@pytest.mark.asyncio
async def test_mistral_maps_provider_neutral_request_and_response():
    client = FakeClient(response())
    provider = MistralLLMProvider(api_key=SecretStr("test-secret"), model="mistral-test", client=client)

    result = await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content="Bonjour")], max_tokens=42))

    assert result.content == "Réponse sûre"
    assert result.model == "mistral-test"
    assert result.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert client.calls[0]["model"] == "mistral-test"
    assert client.calls[0]["messages"] == [{"role": "user", "content": "Bonjour"}]
    assert client.calls[0]["max_tokens"] == 42
    assert "test-secret" not in repr(provider)
    assert "test-secret" not in result.model_dump_json()


def test_mistral_requires_key_and_model():
    with pytest.raises(LLMConfigurationError):
        MistralLLMProvider(api_key=None, model="mistral-test")
    with pytest.raises(LLMConfigurationError):
        MistralLLMProvider(api_key=SecretStr("test-secret"), model=None)


@pytest.mark.asyncio
async def test_mistral_failure_is_controlled_and_does_not_leak_secret():
    client = FakeClient(error=RuntimeError("authorization header test-secret"))
    provider = MistralLLMProvider(api_key=SecretStr("test-secret"), model="mistral-test", client=client)

    with pytest.raises(LLMProviderUnavailableError) as error:
        await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content="Bonjour")]))
    assert "test-secret" not in str(error.value)
