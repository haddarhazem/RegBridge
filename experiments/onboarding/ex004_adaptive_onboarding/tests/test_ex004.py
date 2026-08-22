import json
from pathlib import Path

from experiments.onboarding.ex004_adaptive_onboarding.run_ex004 import DOMAINS, load_scenarios, metrics, scenario_result, v0_domains, v1_domains


def test_frozen_scenario_schema_has_twenty_unique_cases_and_complete_matrices():
    scenarios = load_scenarios()
    assert len(scenarios) == 20
    assert len({scenario["id"] for scenario in scenarios}) == 20
    assert all(set(scenario["expected_relevance"]) == set(DOMAINS) for scenario in scenarios)


def test_v0_is_fixed_and_v1_is_current_deterministic_strategy():
    scenario = load_scenarios()[0]
    assert v0_domains(scenario) == list(DOMAINS)
    assert v1_domains(scenario) == ["activity", "sector", "market", "location"]


def test_variants_are_repeatable_without_provider_or_database():
    scenarios = load_scenarios()
    first = [[scenario_result(scenario, variant) for scenario in scenarios] for variant in ("V0", "V1")]
    second = [[scenario_result(scenario, variant) for scenario in scenarios] for variant in ("V0", "V1")]
    assert first == second


def test_resume_skips_confirmed_fields_only_for_adaptive_variant():
    scenario = next(item for item in load_scenarios() if item["id"] == "ONB-020")
    fixed = scenario_result(scenario, "V0")
    adaptive = scenario_result(scenario, "V1")
    assert set(fixed["repeated_confirmed_domains"]) == {"activity", "sector", "market"}
    assert adaptive["repeated_confirmed_domains"] == []


def test_result_metrics_have_no_business_coaching_domain():
    scenarios = load_scenarios()
    assert set(DOMAINS) == {"activity", "sector", "technology", "data", "market", "location"}
    assert all("growth" not in json.dumps(scenario).lower() for scenario in scenarios)
    assert metrics([scenario_result(scenario, "V1") for scenario in scenarios])["scenario_count"] == 20


def test_corrected_rules_retain_context_for_previous_development_misses():
    scenarios = {scenario["id"]: scenario for scenario in load_scenarios()}
    assert {field for field in v1_domains(scenarios["ONB-002"])} >= {"technology", "data"}
    assert "technology" in set(v1_domains(scenarios["ONB-009"]))
    assert "technology" in set(v1_domains(scenarios["ONB-012"]))


def test_relevant_question_density_is_bounded():
    scenarios = load_scenarios()
    density = metrics([scenario_result(scenario, "V1") for scenario in scenarios])["relevant_question_density"]
    assert 0.0 <= density <= 1.0
