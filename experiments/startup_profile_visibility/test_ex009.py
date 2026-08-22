import json

from experiments.startup_profile_visibility.run_ex009 import (
    ADVERSARIAL,
    CORE,
    _observation,
    load_benchmark,
    run,
    validate_observation,
)


def test_frozen_benchmarks_are_candidate_neutral_and_complete():
    core = load_benchmark(CORE)
    adversarial = load_benchmark(ADVERSARIAL)
    assert core["frozen"] is True
    assert adversarial["frozen"] is True
    assert core["candidate_independent_expectations"] is True
    assert adversarial["candidate_independent_expectations"] is True
    assert len(core["scenarios"]) == 12
    assert len(adversarial["scenarios"]) == 8
    assert len({case["id"] for case in core["scenarios"]}) == 12
    assert len({case["id"] for case in adversarial["scenarios"]}) == 8
    for benchmark in (core, adversarial):
        for case in benchmark["scenarios"]:
            assert case["expected_projection"]["public_fields"] is not None
            assert case["expected_projection"]["hidden_fields"] is not None
            assert case["expected_authorization"]["modify"] in (True, False)
            for field in case["initial_profile_state"]["fields"]:
                assert field["visibility"] in {"PUBLIC", "INVESTOR_SHARED", "PRIVATE"}
            serialized = json.dumps(case.get("expected_invariants", case["expected_projection"]))
            assert "v0_field_level" not in serialized
            assert "v1_section_level" not in serialized


def test_runner_loads_json_and_keeps_core_adversarial_results_separate():
    result = run()
    assert result["metadata"]["benchmark_ids"] == [
        "startup_profile_visibility_ex009_v1",
        "startup_profile_visibility_ex009_adversarial_v1",
    ]
    for candidate in ("v0_field_level", "v1_section_level"):
        assert len(result["candidates"][candidate]["core"]) == 12
        assert len(result["candidates"][candidate]["adversarial"]) == 8


def test_mutation_evaluator_detects_all_required_privacy_failures():
    case = load_benchmark(CORE)["scenarios"][1]
    baseline = _observation(case, "v0_field_level")
    assert baseline["passed"] is True
    mutations = {
        "private_leak": {"public_projection": ["name", "internal_notes"]},
        "investor_leak": {"public_projection": ["name", "funding_target"]},
        "missing_public": {"public_projection": []},
        "unauthorized_edit": {"authorization_correct": False},
        "historical_rewrite": {"history_preserved": False},
        "cross_project_leak": {"cross_project_isolation": False},
    }
    for _name, changes in mutations.items():
        mutated = dict(baseline, **changes)
        assert validate_observation(case, mutated)[0] is False
