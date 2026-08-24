import json
from pathlib import Path

from experiments.opportunity_brief_verification.run_ex023 import evaluate_v0


def test_ex023_frozen_benchmark_and_deterministic_candidate():
    benchmark = json.loads((Path(__file__).parents[2] / "benchmarks/investor_opportunity_brief_ex023_v1.json").read_text(encoding="utf-8"))
    assert benchmark["frozen"] is True
    assert len(benchmark["cases"]) == 24
    result = evaluate_v0(benchmark["cases"])
    assert result["false_pass_rate"] == 0
    assert result["unknown_protection"] is True
    assert result["matching_fidelity_protection"] is True
    assert result["unauthorized_data_usage"] == 0

