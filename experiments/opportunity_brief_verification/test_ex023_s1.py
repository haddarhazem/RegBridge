import json
from pathlib import Path

from experiments.opportunity_brief_verification.run_ex023 import _v0_actual


def test_ex023_s1_labels_are_frozen_and_v0_reaches_fallback_cases():
    benchmark = json.loads((Path(__file__).parents[2] / "benchmarks/investor_opportunity_brief_ex023_s1.json").read_text(encoding="utf-8"))
    assert benchmark["frozen"] is True
    assert len(benchmark["cases"]) == 10
    actual = [_v0_actual(case) for case in benchmark["cases"]]
    assert actual.count("SUPPORTED") == 0
    assert actual.count("UNSUPPORTED") == 5
    assert actual.count("UNVERIFIABLE") == 5

