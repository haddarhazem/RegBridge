"""Run EX-004B on the independent holdout without changing production rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.onboarding.ex004_adaptive_onboarding.run_ex004 import DOMAINS, metrics, scenario_result


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks/adaptive_onboarding_holdout_v1.json"
ARTIFACT = ROOT / "artifacts/experiments/EX-004/ex004b_results.json"


def load_holdout() -> list[dict[str, Any]]:
    payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    if payload["domains"] != list(DOMAINS) or len(payload["scenarios"]) != 12:
        raise ValueError("invalid EX-004B holdout")
    ids = [scenario["id"] for scenario in payload["scenarios"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate EX-004B scenario ID")
    for scenario in payload["scenarios"]:
        if set(scenario["expected_relevance"]) != set(DOMAINS):
            raise ValueError(f"incomplete EX-004B matrix: {scenario['id']}")
    return payload["scenarios"]


def run() -> dict[str, Any]:
    scenarios = load_holdout()
    output = {
        "experiment_id": "EX-004B",
        "benchmark": "adaptive_onboarding_holdout_v1",
        "variants": {
            variant: {
                "metrics": metrics([scenario_result(scenario, variant) for scenario in scenarios]),
                "scenarios": [scenario_result(scenario, variant) for scenario in scenarios],
            }
            for variant in ("V0", "V1")
        },
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
