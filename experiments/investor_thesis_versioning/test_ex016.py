import json
from pathlib import Path
from experiments.investor_thesis_versioning.run_ex016 import evaluate

def test_immutable_candidate_preserves_frozen_invariants():
    root=Path(__file__).parents[2]; benchmark=json.loads((root/"benchmarks/investor_thesis_versioning_ex016_v1.json").read_text())
    assert all(evaluate("V1", item)["history_reproducible"] and evaluate("V1", item)["missing_fields_preserved"] for item in benchmark["scenarios"])

def test_mutation_evaluator_detects_all_frozen_mutations():
    root=Path(__file__).parents[2]; result=json.loads((root/"artifacts/experiments/ex016_investor_thesis_versioning_results.json").read_text())
    assert len(result["mutations"])==8 and all(item["detected"] for item in result["mutations"])
