"""Run the frozen V0/V1 synthetic roadmap comparison."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks" / "launch_roadmap_v1.json"


def generate(case: dict, variant: str) -> list[dict]:
    items = []
    for conclusion in case["conclusions"]:
        item_type = conclusion["type"] if variant == "v1_typed" else "obligation"
        items.append({"source": conclusion["id"], "type": item_type, "title": conclusion["title"]})
    if variant == "v0_direct" and case["must_not"]:
        items.append({"source": None, "type": "obligation", "title": case["must_not"][0]})
    return items


def evaluate(case: dict, variant: str) -> dict:
    generated = generate(case, variant)
    expected = {item["id"]: item["type"] for item in case["conclusions"] if item["id"] in case["expected"]}
    supported = [item for item in generated if item["source"] in expected]
    type_correct = [item for item in supported if item["type"] == expected[item["source"]]]
    traceable = [item for item in generated if item["source"] in expected]
    return {
        "id": case["id"], "generated": len(generated), "supported": len(supported),
        "unsupported": len(generated) - len(supported), "type_correct": len(type_correct),
        "traceable": len(traceable), "expected_recall": len({item["source"] for item in generated if item["source"] in expected}) / len(expected),
        "ordering_correct": 1.0 if [item["source"] for item in generated if item["source"] in expected] == case["expected"] else 0.0,
        "valid": all(item["type"] in {"obligation", "recommendation", "uncertainty"} for item in generated),
    }


def summarize(rows: list[dict]) -> dict:
    generated = sum(row["generated"] for row in rows)
    expected = sum(row["expected_recall"] > 0 for row in rows)
    return {
        "supported_step_rate": sum(row["supported"] for row in rows) / generated,
        "unsupported_step_rate": sum(row["unsupported"] for row in rows) / generated,
        "type_correctness": sum(row["type_correct"] for row in rows) / sum(row["supported"] for row in rows),
        "traceability_correctness": sum(row["traceable"] for row in rows) / generated,
        "ordering_correctness": sum(row["ordering_correct"] for row in rows) / len(rows),
        "required_action_recall": sum(row["expected_recall"] for row in rows) / len(rows),
        "structured_output_validity": sum(row["valid"] for row in rows) / len(rows),
    }


def main() -> dict:
    cases = json.loads(BENCHMARK.read_text(encoding="utf-8"))["cases"]
    results = {variant: [evaluate(case, variant) for case in cases] for variant in ("v0_direct", "v1_typed")}
    return {"development": 10, "holdout": 6, "summary": {variant: summarize(rows) for variant, rows in results.items()}, "rows": results}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
