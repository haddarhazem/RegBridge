from types import SimpleNamespace
import uuid

import pytest
from pydantic import SecretStr

from app.modules.ai.contracts import OrchestrationRequest
from app.modules.ai.llm import LLMGenerationRequest, LLMGenerationResponse, LLMMessage, LLMProviderUnavailableError
from app.modules.ai.orchestration import Orchestrator
from app.modules.ai.providers.mistral import MistralLLMProvider
from app.modules.ai.schemas import AgentRunResponseTrace
from app.modules.regulatory.agent import _execution_payload


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.chat = self

    async def complete_async(self, **kwargs):
        if self.error:
            raise self.error
        return self.response


def provider_response(*, usage=None):
    return SimpleNamespace(
        model="mistral-test",
        choices=[SimpleNamespace(message=SimpleNamespace(content="Réponse"), finish_reason="stop")],
        usage=usage,
    )


@pytest.mark.asyncio
async def test_provider_normalizes_latency_model_prompt_and_usage_without_cost():
    provider = MistralLLMProvider(
        api_key=SecretStr("test-secret"),
        model="mistral-test",
        client=FakeClient( response=provider_response(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15))),
    )
    result = await provider.generate(LLMGenerationRequest(
        messages=[LLMMessage(role="user", content="Bonjour")],
        prompt_version="scrum186-test-v1",
        operation="test_generation",
    ))
    assert result.execution is not None
    assert result.execution.provider == "mistral"
    assert result.execution.logical_model == "mistral-test"
    assert result.execution.prompt_version == "scrum186-test-v1"
    assert result.execution.status == "success"
    assert result.execution.duration_ms is not None
    assert result.execution.total_tokens == 15
    assert result.execution.estimated_cost is None


@pytest.mark.asyncio
async def test_missing_provider_usage_is_safe_and_cost_stays_null():
    provider = MistralLLMProvider(api_key=SecretStr("test-secret"), model="mistral-test", client=FakeClient(response=provider_response()))
    result = await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content="Bonjour")]))
    assert result.execution is not None
    assert result.execution.prompt_tokens is None
    assert result.execution.completion_tokens is None
    assert result.execution.total_tokens is None
    assert result.execution.estimated_cost is None


@pytest.mark.asyncio
async def test_provider_failure_has_bounded_category_and_no_secret():
    provider = MistralLLMProvider(api_key=SecretStr("test-secret"), model="mistral-test", client=FakeClient(error=RuntimeError("test-secret")))
    with pytest.raises(LLMProviderUnavailableError) as caught:
        await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content="Bonjour")], prompt_version="v1"))
    error = caught.value
    assert error.category == "provider_unavailable"
    assert error.duration_ms is not None
    assert "test-secret" not in str(error)


def test_trace_projection_contains_metadata_and_sources_but_no_prompt_or_private_content():
    payload = {
        "generation_status": "success",
        "generation_provider": "mistral",
        "generation_logical_model": "mistral-test",
        "generation_prompt_version": "scrum184-regulatory-answer-v1",
        "generation_total_tokens": 15,
        "generation_estimated_cost": None,
        "source_ids": "point-1|point-2",
    }
    trace = AgentRunResponseTrace(summary="safe", result=payload)
    serialized = trace.model_dump_json()
    assert "point-1" in serialized
    assert "private document text" not in serialized
    assert "USER QUESTION" not in serialized
    assert "test-secret" not in serialized


def test_request_conversation_message_and_agent_correlation_are_traceable():
    request = OrchestrationRequest(
        request_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        intent_hint="regulatory",
    )
    trace = Orchestrator._trace_request("regulatory", request)
    refs = {item.resource_type: item.resource_id for item in trace.context_refs}
    assert refs["conversation"] == request.conversation_id
    assert refs["message"] == request.message_id
    assert request.request_id is not request.conversation_id


def test_execution_payload_is_allowlisted_and_does_not_contain_request_body():
    response = LLMGenerationResponse(content="answer", model="model")
    payload = _execution_payload("generation", response.execution)
    assert "generation_prompt_text" not in payload
    assert "generation_estimated_cost" in payload
