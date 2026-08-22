"""Run the frozen V0/V1 adaptive-onboarding comparison."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.modules.projects.onboarding import next_questions


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks/adaptive_onboarding_v1.json"
ARTIFACT_DIR = ROOT / "artifacts/experiments/EX-004"
DOMAINS = ("activity", "sector", "technology", "data", "market", "location")


def load_scenarios() -> list[dict[str, Any]]:
    payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    if payload["domains"] != list(DOMAINS) or len(payload["scenarios"]) != 20:
        raise ValueError("invalid frozen EX-004 scenario set")
    ids = [scenario["id"] for scenario in payload["scenarios"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate EX-004 scenario ID")
    for scenario in payload["scenarios"]:
        if set(scenario["expected_relevance"]) != set(DOMAINS):
            raise ValueError(f"incomplete expected relevance matrix: {scenario['id']}")
        if any(value not in {"required", "not_required"} for value in scenario["expected_relevance"].values()):
            raise ValueError(f"invalid relevance value: {scenario['id']}")
        if not set(scenario.get("initial_confirmed", [])).issubset(DOMAINS):
            raise ValueError(f"invalid initial confirmation: {scenario['id']}")
    return payload["scenarios"]


def snapshot(scenario: dict[str, Any]) -> SimpleNamespace:
    confirmed = {field: "confirmed" for field in scenario.get("initial_confirmed", [])}
    return SimpleNamespace(
        activity=scenario.get("activity"),
        sector=scenario.get("sector"),
        technology=scenario.get("technology"),
        data_context=scenario.get("data"),
        target_market=scenario.get("target_market"),
        location=scenario.get("location"),
        confirmed_fields=confirmed,
    )


def v0_domains(scenario: dict[str, Any]) -> list[str]:
    """Fixed questionnaire: all six domains, including resumed fields."""

    return list(DOMAINS)


def v1_domains(scenario: dict[str, Any]) -> list[str]:
    return [question.field for question in next_questions(snapshot(scenario))]


def scenario_result(scenario: dict[str, Any], variant: str) -> dict[str, Any]:
    selected = v0_domains(scenario) if variant == "V0" else v1_domains(scenario)
    expected = scenario["expected_relevance"]
    relevant = {field for field, value in expected.items() if value == "required"}
    initial = set(scenario.get("initial_confirmed", []))
    collected = initial | set(selected)
    relevant_asked = len((set(selected) & relevant) | (initial & relevant))
    irrelevant_asked = len(set(selected) - relevant)
    repeated = len(set(selected) & initial)
    remaining = relevant - collected
    completion_questions = None if remaining else len(selected)
    return {
        "scenario_id": scenario["id"],
        "expected_relevant_domains": sorted(relevant),
        "initial_confirmed": sorted(initial),
        "selected_domains": selected,
        "relevant_asked": relevant_asked,
        "irrelevant_asked": irrelevant_asked,
        "repeated_confirmed_domains": sorted(set(selected) & initial),
        "completion_questions": completion_questions,
    }


def metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_relevant = sum(len(row["expected_relevant_domains"]) for row in results)
    total_relevant_collected = sum(row["relevant_asked"] for row in results)
    total_asked = sum(len(row["selected_domains"]) for row in results)
    total_irrelevant = sum(row["irrelevant_asked"] for row in results)
    total_relevant_questions = sum(
        len(set(row["selected_domains"]) & set(row["expected_relevant_domains"])) for row in results
    )
    confirmed_total = sum(len(row["initial_confirmed"]) for row in results)
    repeated_total = sum(len(row["repeated_confirmed_domains"]) for row in results)
    completion = [row["completion_questions"] for row in results if row["completion_questions"] is not None]
    return {
        "scenario_count": len(results),
        "required_context_coverage": total_relevant_collected / total_relevant if total_relevant else 1.0,
        "irrelevant_question_rate": total_irrelevant / total_asked if total_asked else 0.0,
        "average_questions": total_asked / len(results),
        "relevant_question_density": total_relevant_questions / total_asked if total_asked else 1.0,
        "repeated_question_rate": repeated_total / confirmed_total if confirmed_total else 0.0,
        "resume_cases": sum(bool(row["initial_confirmed"]) for row in results),
        "completion_cases": len(completion),
        "average_completion_questions": statistics.mean(completion) if completion else None,
    }


def run() -> dict[str, Any]:
    scenarios = load_scenarios()
    per_scenario = {variant: [scenario_result(scenario, variant) for scenario in scenarios] for variant in ("V0", "V1")}
    output = {
        "experiment_id": "EX-004",
        "benchmark": "adaptive_onboarding_v1",
        "variants": {variant: {"metrics": metrics(rows), "scenarios": rows} for variant, rows in per_scenario.items()},
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "ex004_results.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
