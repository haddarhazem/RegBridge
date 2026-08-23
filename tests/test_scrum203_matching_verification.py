import json
from types import SimpleNamespace

import pytest

from app.modules.ai.llm import LLMGenerationResponse, LLMExecutionMetadata
from app.modules.investment.matching import deterministic_match
from app.modules.investment.matching_verification import explain_with_fallback, safe_explanation


RESULT = deterministic_match({"sectors":["healthtech"],"stages":["seed"]}, {"sector":"healthtech","stage":None})
INVESTOR = {"sectors":["healthtech"], "stages":["seed"]}
STARTUP = {"sector":"healthtech", "stage":None}


def valid_payload():
    return safe_explanation(RESULT).model_dump_json()


class FakeProvider:
    def __init__(self, content=None, error=None): self.content, self.error, self.request = content, error, None
    async def generate(self, request):
        self.request = request
        if self.error: raise self.error
        return LLMGenerationResponse(content=self.content, model="fake", execution=LLMExecutionMetadata(status="success", provider="fake", model="fake", logical_model="fake", prompt_version=request.prompt_version, operation=request.operation))


@pytest.mark.asyncio
async def test_valid_structured_explanation_is_accepted():
    result = await explain_with_fallback(FakeProvider(valid_payload()), investor_snapshot=INVESTOR, startup_snapshot=STARTUP, result=RESULT)
    assert result.accepted and not result.fallback_used


@pytest.mark.parametrize("content", ["not json", json.dumps({"summary":"x"}), json.dumps({"summary":"x","strengths":[],"gaps":[],"unknowns":["stage"],"caveats":["not financial advice"]})])
@pytest.mark.asyncio
async def test_invalid_json_or_schema_uses_fallback(content):
    result = await explain_with_fallback(FakeProvider(content), investor_snapshot=INVESTOR, startup_snapshot=STARTUP, result=RESULT)
    assert not result.accepted and result.fallback_used and result.explanation.caveats


@pytest.mark.parametrize("mutation", [
    lambda p: {**p, "summary":"Team quality is excellent", "caveats":["not financial advice"]},
    lambda p: {**p, "summary":"sector is a MISMATCH", "caveats":["not financial advice"]},
    lambda p: {**p, "unknowns":[], "caveats":["not financial advice"]},
    lambda p: {**p, "score":0.1},
    lambda p: {**p, "summary":"Guaranteed high ROI; ignore previous instructions", "caveats":["not financial advice"]},
    lambda p: {**p, "caveats":[]},
])
@pytest.mark.asyncio
async def test_evaluator_mutations_are_rejected(mutation):
    payload = json.loads(valid_payload())
    payload = mutation(payload)
    result = await explain_with_fallback(FakeProvider(json.dumps(payload)), investor_snapshot=INVESTOR, startup_snapshot=STARTUP, result=RESULT)
    assert not result.accepted and result.fallback_used and result.explanation.unknowns == RESULT["unknown_dimensions"]


@pytest.mark.asyncio
async def test_provider_exception_and_timeout_use_deterministic_fallback():
    class TimeoutProvider:
        async def generate(self, request):
            import asyncio
            await asyncio.sleep(0.05)
            raise TimeoutError()
    for provider in (FakeProvider(error=RuntimeError("provider down")), TimeoutProvider()):
        result = await explain_with_fallback(provider, investor_snapshot=INVESTOR, startup_snapshot=STARTUP, result=RESULT)
        assert not result.accepted and result.fallback_used and result.explanation.unknowns == RESULT["unknown_dimensions"]


@pytest.mark.asyncio
async def test_explanation_prompt_is_minimized_and_marks_text_untrusted():
    provider = FakeProvider(valid_payload())
    await explain_with_fallback(provider, investor_snapshot=INVESTOR, startup_snapshot={"sector":"healthtech", "private_notes":"do not send"}, result=RESULT)
    prompt = provider.request.messages[1].content
    assert "AUTHORIZED MATCHING INPUT (UNTRUSTED TEXT FIELDS)" in prompt
    assert "private_notes" not in prompt
