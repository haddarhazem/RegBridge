import json

import pytest

from app.modules.investment.brief_generation import DISCLAIMER, deterministic_generation, generate_with_fallback, validate_generation
from app.modules.investment.brief_schemas import BriefEvidenceBundle


MATCHING = {
    "matching_method": "structured_v1",
    "matching_method_version": "1",
    "score": 0.8,
    "score_formula": "matches / comparable_dimensions; UNKNOWN excluded",
    "dimensions": {"sector": "MATCH", "stage": "UNKNOWN", "geography": "MATCH", "technology": "MATCH", "ticket": "MISMATCH"},
    "unknown_dimensions": ["stage"],
}


def bundle() -> BriefEvidenceBundle:
    return BriefEvidenceBundle(
        investor_thesis={"sectors": ["healthtech"]},
        startup_snapshot={"sector": "healthtech", "stage": None, "geography": "France", "technology": "AI", "funding_need": 900000},
        confirmed_facts=[{"evidence_ref": "project_fact:1", "domain": "sector", "value": "healthtech", "status": "confirmed"}],
        matching_result=MATCHING,
        missing_information=["confirmed startup stage"],
        evidence_refs=["project_fact:1", "matching:1:sector"],
    )


class FakeProvider:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.request = None

    async def generate(self, request):
        self.request = request
        if self.error:
            raise self.error
        from app.modules.ai.llm import LLMExecutionMetadata, LLMGenerationResponse
        return LLMGenerationResponse(content=self.content, model="mistral-test", execution=LLMExecutionMetadata(provider="mistral", model="mistral-test", logical_model="mistral-test", status="success"))


def valid_content():
    return json.dumps({
        "executive_summary": "Authorized startup evidence indicates a preliminary fit.",
        "thesis_fit_summary": "The available evidence describes a preliminary fit.",
        "investment_highlights": [{"text": "sector: healthtech", "evidence_refs": ["project_fact:1"]}],
        "matching_acknowledgements": [{"dimension": "sector", "outcome": "MATCH"}, {"dimension": "stage", "outcome": "UNKNOWN"}, {"dimension": "geography", "outcome": "MATCH"}, {"dimension": "technology", "outcome": "MATCH"}, {"dimension": "ticket", "outcome": "MISMATCH"}],
    })


def test_deterministic_brief_has_five_sections_and_disclaimer():
    generated = deterministic_generation(bundle())
    assert [(item.dimension, item.outcome) for item in generated.matching_acknowledgements] == [("sector", "MATCH"), ("stage", "UNKNOWN"), ("geography", "MATCH"), ("technology", "MATCH"), ("ticket", "MISMATCH")]
    assert DISCLAIMER.startswith("This brief is based only")


@pytest.mark.asyncio
async def test_json_schema_generation_is_accepted_and_prompt_is_minimized():
    provider = FakeProvider(valid_content())
    generated, accepted, issues, _, rejected, rejected_refs = await generate_with_fallback(provider, bundle())
    assert accepted and not issues
    assert provider.request.response_format["type"] == "json_schema"
    assert "raw_description" not in provider.request.messages[1].content
    assert generated.matching_acknowledgements[1].outcome == "UNKNOWN"
    assert rejected is None and rejected_refs == []


@pytest.mark.asyncio
async def test_invalid_generation_falls_back_and_keeps_matching():
    provider = FakeProvider(json.dumps({"executive_summary": "invented revenue and high ROI"}))
    generated, accepted, issues, _, rejected, _ = await generate_with_fallback(provider, bundle())
    assert not accepted and issues
    assert generated.matching_acknowledgements[1].outcome == "UNKNOWN"
    assert rejected is not None


@pytest.mark.asyncio
async def test_provider_failure_falls_back():
    generated, accepted, issues, _, _, _ = await generate_with_fallback(FakeProvider(error=TimeoutError()), bundle())
    assert not accepted and "provider failure" in issues
    assert generated.matching_acknowledgements[-1].outcome == "MISMATCH"


@pytest.mark.parametrize("outcome", ["MATCH", "MISMATCH", "UNKNOWN"])
def test_structured_matching_outcome_is_authoritative(outcome):
    payload = json.loads(valid_content())
    payload["matching_acknowledgements"][0]["outcome"] = outcome
    parsed, issues, _, _ = validate_generation(json.dumps(payload), bundle())
    if outcome == "MATCH":
        assert parsed is not None and not issues
    else:
        assert parsed is None and "matching fidelity failure" in issues


def test_faithful_prose_paraphrase_is_not_used_for_matching_validation():
    payload = json.loads(valid_content())
    payload["thesis_fit_summary"] = "The available information suggests alignment, while one stage is not yet available."
    parsed, issues, _, _ = validate_generation(json.dumps(payload), bundle())
    assert parsed is not None and not issues


def test_invented_dimension_is_rejected():
    payload = json.loads(valid_content())
    payload["matching_acknowledgements"][0] = {"dimension": "ticket", "outcome": "MATCH"}
    parsed, issues, _, _ = validate_generation(json.dumps(payload), bundle())
    assert parsed is None and "matching fidelity failure" in issues


def test_unknown_evidence_reference_is_rejected_and_retained():
    payload = json.loads(valid_content())
    payload["investment_highlights"][0]["evidence_refs"] = ["fact:unknown"]
    parsed, issues, raw, refs = validate_generation(json.dumps(payload), bundle())
    assert parsed is None and "unsupported evidence reference" in issues
    assert raw is not None and refs == ["fact:unknown"]
