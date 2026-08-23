import json
from pathlib import Path
from experiments.startup_visibility_search.run_ex017 import evaluate

def test_prefiltered_candidate_preserves_privacy_invariants():
    root=Path(__file__).parents[2]; benchmark=json.loads((root/"benchmarks/startup_visibility_search_ex017_v1.json").read_text())
    assert all(not evaluate("V0",item)["unauthorized_influence"] for item in benchmark["scenarios"])

def test_mutations_are_detected():
    root=Path(__file__).parents[2]; result=json.loads((root/"artifacts/experiments/ex017_startup_visibility_search_results.json").read_text())
    assert len(result["mutations"])==10 and all(item["detected"] for item in result["mutations"])
