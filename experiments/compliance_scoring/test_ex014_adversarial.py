import json
from pathlib import Path

def test_all_frozen_adversarial_mutations_are_detected():
    root = Path(__file__).parents[2]
    benchmark = json.loads((root / "benchmarks/compliance_scoring_ex014_adversarial_v1.json").read_text())
    results = json.loads((root / "artifacts/experiments/ex014_compliance_scoring_results.json").read_text())
    assert [x["scenario_id"] for x in results["adversarial"]] == [x["scenario_id"] for x in benchmark["scenarios"]]
    assert all(x["detected"] for x in results["adversarial"])
