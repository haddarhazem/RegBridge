import json
from pathlib import Path

from experiments.contact_consent.run_ex020 import evaluate


ROOT = Path(__file__).parents[2]


def test_ex020_benchmarks_are_frozen_and_complete():
    core = json.loads((ROOT / "benchmarks/contact_consent_ex020_v1.json").read_text(encoding="utf-8"))
    adversarial = json.loads((ROOT / "benchmarks/contact_consent_ex020_adversarial_v1.json").read_text(encoding="utf-8"))
    assert len(core) == 12 and len(adversarial) == 12
    assert len({case["id"] for case in core}) == 12
    assert len({case["id"] for case in adversarial}) == 12


def test_ex020_candidates_have_no_unauthorized_disclosure_in_protocol():
    scenarios = json.loads((ROOT / "benchmarks/contact_consent_ex020_v1.json").read_text(encoding="utf-8"))
    for candidate in ("V0", "V1"):
        result = evaluate(candidate, scenarios)
        assert result["passed"] == 12
        assert result["unauthorized_disclosures"] == 0
