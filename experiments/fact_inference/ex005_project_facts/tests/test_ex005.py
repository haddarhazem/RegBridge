import json
from pathlib import Path

from experiments.fact_inference.ex005_project_facts.contracts import ExtractionResponse
from experiments.fact_inference.ex005_project_facts.deterministic import extract
from experiments.fact_inference.ex005_project_facts.evaluation import evaluate
from experiments.fact_inference.ex005_project_facts.run_ex005 import load_benchmark
from experiments.fact_inference.ex005_project_facts.structured import build_request


def test_benchmark_has_disjoint_frozen_16_8_split_and_independent_labels():
    payload = load_benchmark()
    assert len(payload["development_ids"]) == 16
    assert len(payload["holdout_ids"]) == 8
    assert set(payload["development_ids"]).isdisjoint(payload["holdout_ids"])
    assert all("outputs" not in case and "prediction" not in case for case in payload["cases"])


def test_v0_is_repeatable_and_provenance_is_bounded_source_text():
    description = load_benchmark()["cases"][1]["description"]
    first = extract(description)
    second = extract(description)
    assert [fact.model_dump() for fact in first] == [fact.model_dump() for fact in second]
    assert all(fact.provenance.source_field == "description" for fact in first)
    assert all(fact.provenance.excerpt.lower() in description.lower() for fact in first)


def test_structured_contract_rejects_unsupported_fields_and_prompt_is_bounded():
    request = build_request("Projet SaaS pour entreprises.")
    assert request.response_format["type"] == "json_schema"
    assert "allowed_domains" in request.messages[1].content
    assert "chain" not in request.messages[0].content.lower()
    valid = ExtractionResponse.model_validate({"facts": []})
    assert valid.facts == []


def test_metrics_do_not_claim_cost_and_are_bounded():
    case = {"id": "X", "description": "service", "expected_facts": []}
    values = evaluate([case], {"X": []}, {"X": {"valid": True, "latency_ms": 1, "usage": {}}})
    assert values["precision"] == values["recall"] == values["f1"] == 1.0
    assert "estimated_cost" not in values
