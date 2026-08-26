import json
from pathlib import Path

from .matcher import metrics, rank
from .audit_ex025 import _query_values

ROOT = Path(__file__).parents[2]


def data():
    return json.loads((ROOT / "benchmarks/research_matching_ex025_v1.json").read_text(encoding="utf-8"))


def test_benchmark_is_frozen_and_complete():
    benchmark = data()
    assert len(benchmark["needs"]) == 24
    assert len(benchmark["research_snapshots"]) == 30
    assert len(benchmark["holdout_need_ids"]) == 16
    assert len(benchmark["development_need_ids"]) == 8
    assert len(benchmark["zero_relevant_need_ids"]) == 4
    assert len({row["id"] for row in benchmark["needs"]}) == 24
    assert len({row["id"] for row in benchmark["research_snapshots"]}) == 30


def test_structured_matching_is_deterministic_and_ties_are_stable():
    benchmark = data(); need = benchmark["needs"][0]
    first = rank(need, benchmark["research_snapshots"], "V0")
    second = rank(need, benchmark["research_snapshots"], "V0")
    assert [row["id"] for row in first] == [row["id"] for row in second]
    assert first[0]["id"] == "R01"


def test_unknown_fields_do_not_become_negative_evidence():
    benchmark = data(); need = {"domains": ["health"]}
    rows = rank(need, benchmark["research_snapshots"], "V0")
    assert rows[0]["score"] >= 0


def test_metrics_include_zero_relevant_queries():
    benchmark = data()
    result = metrics(benchmark, "V0", benchmark["holdout_need_ids"])
    assert set(result) == {"P@5", "R@5", "HitRate@5", "MRR", "nDCG@5"}


def test_metric_audit_reports_zero_match_and_oracle_ceiling():
    benchmark = data()
    assert all(_query_values(benchmark, "V0", need_id, 5)["relevant"] == 0 for need_id in benchmark["zero_relevant_need_ids"])
    assert sum(_query_values(benchmark, "V0", need_id, 5)["oracle_precision"] for need_id in benchmark["holdout_need_ids"]) / len(benchmark["holdout_need_ids"]) < 0.70
