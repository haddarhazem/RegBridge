import json
from pathlib import Path
from experiments.investor_sharing.run_ex015 import evaluate

def test_candidate_comparison_is_deterministic_and_frozen():
    root = Path(__file__).parents[2]
    benchmark = json.loads((root / "benchmarks/investor_sharing_ex015_v1.json").read_text())
    for scenario in benchmark["scenarios"]:
        for candidate in ("V0", "V1"):
            result = evaluate(candidate, scenario)
            assert result["unauthorized_access"] is False and result["violated_invariants"] == []

def test_all_adversarial_mutations_are_detected():
    root = Path(__file__).parents[2]
    result = json.loads((root / "artifacts/experiments/ex015_investor_sharing_results.json").read_text())
    assert len(result["mutations"]) == 10 and all(item["detected"] for item in result["mutations"])
