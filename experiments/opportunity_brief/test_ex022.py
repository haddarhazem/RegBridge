import json
from pathlib import Path

from app.modules.investment.brief_generation import deterministic_generation
from app.modules.investment.brief_schemas import BriefEvidenceBundle


def test_ex022_benchmark_is_reproducible_and_small():
    data = json.loads((Path(__file__).parents[2] / "benchmarks/investor_opportunity_brief_ex022_v1.json").read_text(encoding="utf-8"))
    assert len(data["cases"]) == 10
    outputs = [deterministic_generation(BriefEvidenceBundle.model_validate(case["bundle"])).model_dump() for case in data["cases"]]
    assert outputs == [deterministic_generation(BriefEvidenceBundle.model_validate(case["bundle"])).model_dump() for case in data["cases"]]
    assert outputs[2]["matching_acknowledgements"][1]["outcome"] == "UNKNOWN"
