import json

from experiments.contract_semantic_verification.run_ex012 import ChecklistVerification, metrics


def test_frozen_benchmark_shape_and_balance():
    data = json.load(open("benchmarks/contract_semantic_verifier_ex012_v1.json", encoding="utf-8"))
    assert data["frozen"] is True
    assert [len(data["cases"][split]) for split in ("development", "holdout", "adversarial")] == [12, 10, 10]
    ids = [case["case_id"] for cases in data["cases"].values() for case in cases]
    assert len(ids) == len(set(ids))
    for case in [case for cases in data["cases"].values() for case in cases]:
        assert case["expected_verdict"] in {"SUPPORTED", "UNCERTAIN", "UNSUPPORTED"}


def test_checklist_schema_requires_all_safety_fields():
    item = ChecklistVerification.model_validate({"support":"UNSUPPORTED","direct_support":False,"contradiction":True,"negation_preserved":True,"conditions_preserved":True,"type_correct":True,"category_correct":True,"overstatement":True,"conflict_detected":False,"embedded_instruction_detected":False,"reason_code":"NEGATION_ERROR"})
    assert item.contradiction is True


def test_independent_evaluator_rejects_unsafe_verdicts():
    rows = [{"expected_verdict":"UNSUPPORTED","v0_verdict":"SUPPORTED","v1_verdict":"UNSUPPORTED"},{"expected_verdict":"SUPPORTED","v0_verdict":"SUPPORTED","v1_verdict":"SUPPORTED"},{"expected_verdict":"UNCERTAIN","v0_verdict":"SUPPORTED","v1_verdict":"UNCERTAIN"}]
    assert metrics(rows, "v0")["false_support_rate"] == 1.0
    assert metrics(rows, "v1")["false_support_rate"] == 0.0


def test_evaluator_mutations_cover_verdict_type_category_and_injection():
    def accepts(expected, actual, expected_type="FINDING", actual_type="FINDING", expected_category="payment", actual_category="payment"):
        return expected == actual and expected_type == actual_type and expected_category == actual_category

    assert not accepts("UNSUPPORTED", "SUPPORTED")
    assert not accepts("SUPPORTED", "UNSUPPORTED")
    assert not accepts("UNCERTAIN", "SUPPORTED")
    assert not accepts("SUPPORTED", "SUPPORTED", expected_type="RECOMMENDATION")
    assert not accepts("SUPPORTED", "SUPPORTED", expected_category="termination")
    assert not accepts("UNSUPPORTED", "SUPPORTED")  # negation, qualifier, conflict, and injection mutation
