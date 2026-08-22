import json

from experiments.contract_extraction.run_ex010 import ADVERSARIAL, CORE, load_benchmark, mutation_detected, run


def test_frozen_split_and_taxonomy_are_candidate_neutral():
    core = load_benchmark(CORE)
    adversarial = load_benchmark(ADVERSARIAL)
    assert core["frozen"] is True
    assert adversarial["frozen"] is True
    assert core["candidate_neutral_expectations"] is True
    assert adversarial["candidate_neutral_expectations"] is True
    assert len(core["cases"]["development"]) == 12
    assert len(core["cases"]["holdout"]) == 8
    assert len(adversarial["cases"]) == 8
    ids = [case["case_id"] for case in core["cases"]["development"] + core["cases"]["holdout"] + adversarial["cases"]]
    assert len(ids) == len(set(ids))
    for case in core["cases"]["development"] + core["cases"]["holdout"] + adversarial["cases"]:
        assert case["document_version"] == "V1"
        assert "expected_findings" in case and "forbidden_categories" in case
        serialized = json.dumps(case["expected_findings"])
        assert "v0_direct_prompting" not in serialized
        assert "v1_structured_extraction" not in serialized
        assert "v2_structured_evidence" not in serialized


def test_runner_keeps_development_holdout_and_adversarial_separate():
    result = run()
    for candidate in ("v0_direct_prompting", "v1_structured_extraction", "v2_structured_evidence"):
        assert len(result["candidates"][candidate]["development"]) == 12
        assert len(result["candidates"][candidate]["holdout"]) == 8
        assert len(result["candidates"][candidate]["adversarial"]) == 8


def test_evaluator_detects_all_required_mutations():
    case = load_benchmark(CORE)["cases"]["development"][0]
    for mutation in ("invented_finding", "wrong_category", "wrong_type", "unrelated_evidence", "offset_quote_mismatch", "negation_error", "wrong_document_version", "missing_finding"):
        assert mutation_detected(case, "v2_structured_evidence", mutation) is True
