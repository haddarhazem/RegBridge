import json

from experiments.project_lifecycle.ex008_project_lifecycle.run_ex008 import (
    ADVERSARIAL,
    ORIGINAL,
    evaluate_scenario,
    load_benchmark,
    run,
    validate_observation,
)


def test_benchmarks_are_frozen_and_candidate_neutral():
    original = load_benchmark(ORIGINAL)
    adversarial = load_benchmark(ADVERSARIAL)

    assert original["frozen"] is True
    assert adversarial["frozen"] is True
    assert original["candidate_independent_expectations"] is True
    assert adversarial["candidate_independent_expectations"] is True
    assert len(original["scenarios"]) == 12
    assert len(adversarial["scenarios"]) == 10
    assert len({case["id"] for case in original["scenarios"]}) == 12
    assert len({case["id"] for case in adversarial["scenarios"]}) == 10

    for benchmark in (original, adversarial):
        for case in benchmark["scenarios"]:
            assert case["initial_project_state"]["lifecycle"] in {
                "idea",
                "startup_in_creation",
                "existing_startup",
            }
            assert case["requested_transition"]["from"] in {
                "idea",
                "startup_in_creation",
                "existing_startup",
            }
            assert case["requested_transition"]["to"]
            assert case["expected_transition_validity"] in (True, False)
            assert case["expected_invariants"]["expected_duplication_behavior"] == "zero"
            serialized = json.dumps(case["expected_invariants"])
            assert "v0_same_project" not in serialized
            assert "v1_linked_project" not in serialized


def test_runs_both_candidates_against_both_json_benchmarks():
    result = run()

    assert result["metadata"]["benchmark_ids"] == [
        "project_lifecycle_ex008_v1",
        "project_lifecycle_ex008_adversarial_v1",
    ]
    for candidate in ("v0_same_project", "v1_linked_project"):
        assert len(result["candidates"][candidate]["original"]) == 12
        assert len(result["candidates"][candidate]["adversarial"]) == 10


def test_mutations_are_detected_by_candidate_independent_evaluator():
    case = load_benchmark(ORIGINAL)["scenarios"][5]
    baseline = evaluate_scenario(case, "v0_same_project")
    assert baseline["passed"] is True

    for field in (
        "identity_continuity",
        "history_preservation",
        "authorization_correctness",
        "reference_integrity",
        "audit_completeness",
        "transition_correctness",
        "idempotency",
        "concurrency_safety",
    ):
        mutated = dict(baseline, **{field: False})
        assert validate_observation(case, mutated)[0] is False

    mutated = dict(baseline, duplication_count=1)
    assert validate_observation(case, mutated)[0] is False


def test_named_adversarial_mutations_are_detected():
    case = load_benchmark(ADVERSARIAL)["scenarios"][-1]
    baseline = evaluate_scenario(case, "v0_same_project")
    mutations = {
        "dropped_assessment_reference": "reference_integrity",
        "duplicate_membership": "duplication_count",
        "missing_audit": "audit_completeness",
        "unauthorized_access": "authorization_correctness",
        "changed_historical_snapshot": "history_preservation",
    }
    for _mutation_name, field in mutations.items():
        value = 1 if field == "duplication_count" else False
        mutated = dict(baseline, **{field: value})
        assert validate_observation(case, mutated)[0] is False
