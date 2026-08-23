import json
from pathlib import Path
from .matcher import match

ROOT = Path(__file__).parents[2]


def test_frozen_benchmark_has_20_pairs_and_16_4_split():
    data = json.loads((ROOT / "benchmarks/investor_startup_matching_ex021_v1.json").read_text(encoding="utf-8"))
    assert len(data["development_pairs"]) == 20
    assert len(data["holdout_pair_ids"]) == 4
    assert len({pair["pair_id"] for pair in data["development_pairs"]}) == 20


def test_deterministic_core_agreement_is_complete():
    data = json.loads((ROOT / "benchmarks/investor_startup_matching_ex021_v1.json").read_text(encoding="utf-8"))
    for pair in data["development_pairs"]:
        actual = match(pair["investor_snapshot"], pair["startup_snapshot"])
        assert actual["dimensions"] == {key: pair["expected"][key] for key in ("sector", "stage", "geography", "technology", "ticket")}
        assert actual["score"] == pair["expected"]["score"]


def test_unknown_is_not_mismatch_and_private_field_is_not_used():
    data = json.loads((ROOT / "benchmarks/investor_startup_matching_ex021_v1.json").read_text(encoding="utf-8"))
    pair = next(item for item in data["development_pairs"] if item["pair_id"] == "M20")
    actual = match(pair["investor_snapshot"], pair["startup_snapshot"])
    assert "private_internal_notes" not in actual
    assert match({"sectors":["healthtech"]}, {"sector":"healthtech"})["dimensions"]["stage"] == "UNKNOWN"
