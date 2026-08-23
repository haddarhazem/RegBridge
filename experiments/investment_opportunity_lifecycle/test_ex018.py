import json
from pathlib import Path
from experiments.investment_opportunity_lifecycle.run_ex018 import evaluate

def test_v1_preserves_frozen_lifecycle_invariants():
    root = Path(__file__).parents[2]
    benchmark = json.loads((root / "benchmarks/investment_opportunity_lifecycle_ex018_v1.json").read_text())
    rows = [evaluate("V1", item) for item in benchmark["scenarios"]]
    assert all(row["history_reproducible"] and row["snapshot_correct"] and row["concurrency_correct"] for row in rows)

def test_all_adversarial_mutations_are_detected():
    root = Path(__file__).parents[2]
    result = json.loads((root / "artifacts/experiments/ex018_investment_opportunity_lifecycle_results.json").read_text())
    assert len(result["mutations"]) == 8 and all(item["detected"] for item in result["mutations"])
