import json
from pathlib import Path
from experiments.event_registration_consistency.run_ex019 import evaluate

def test_v0_satisfies_frozen_participation_invariants():
    root = Path(__file__).parents[2]; benchmark = json.loads((root / "benchmarks/event_registration_consistency_ex019_v1.json").read_text())
    assert all(evaluate("V0", item)["duplicate_free"] and evaluate("V0", item)["audit_complete"] for item in benchmark["scenarios"])

def test_all_adversarial_mutations_are_detected():
    root = Path(__file__).parents[2]; result = json.loads((root / "artifacts/experiments/ex019_event_registration_consistency_results.json").read_text())
    assert len(result["mutations"]) == 10 and all(item["detected"] for item in result["mutations"])
