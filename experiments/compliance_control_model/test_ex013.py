import json

from experiments.compliance_control_model.run_ex013 import mutation_detected, run


def test_frozen_benchmarks_have_required_shape():
    core = json.load(open("benchmarks/compliance_control_model_ex013_v1.json", encoding="utf-8"))
    adversarial = json.load(open("benchmarks/compliance_control_model_ex013_adversarial_v1.json", encoding="utf-8"))
    assert core["frozen"] and adversarial["frozen"]
    assert len(core["scenarios"]) == 12
    assert len(adversarial["scenarios"]) == 8


def test_evaluator_detects_required_mutations():
    scenario = json.load(open("benchmarks/compliance_control_model_ex013_adversarial_v1.json", encoding="utf-8"))["scenarios"][0]
    for mutation in ("revoked_active", "wrong_version", "historical_rewrite", "cross_project", "source_loss", "framework_contamination", "silent_upgrade"):
        assert mutation_detected(scenario, mutation)


def test_runner_keeps_candidates_and_splits_separate():
    result = run()
    assert set(result["candidates"]) == {"materialized", "dynamic"}
    assert all(len(result["candidates"][candidate]["core"]) == 12 for candidate in result["candidates"])
    assert all(len(result["candidates"][candidate]["adversarial"]) == 8 for candidate in result["candidates"])
