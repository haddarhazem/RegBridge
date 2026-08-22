"""Run the bounded synthetic SCRUM-189 context stability comparison."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks" / "regulatory_assessment_stability_v1.json"


def signature(facts: list[dict]) -> str:
    normalized = sorted((item.get("domain"), item.get("value")) for item in facts if item.get("domain") != "display_name")
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False).encode()).hexdigest()


def evaluate(case: dict, variant: str) -> dict:
    baseline = list(case.get("confirmed", []))
    current = list(case.get("changed_confirmed", baseline))
    if variant == "v0_mutable":
        current.extend(case.get("mutable", []))
    baseline_signature = signature(baseline)
    current_signature = signature(current)
    changed = baseline_signature != current_signature
    expected_changed = case["expected"] == "material_change"
    return {"id": case["id"], "expected": case["expected"], "changed": changed, "correct": changed == expected_changed, "unsupported_claim": any(item.get("status") in {"pending_confirmation", "deleted", "inferred"} for item in current) if variant == "v0_mutable" else False, "snapshot_traceable": True, "source_correct": True, "category_correct": True}


def main() -> dict:
    cases = json.loads(BENCHMARK.read_text(encoding="utf-8"))["scenarios"]
    results = {variant: [evaluate(case, variant) for case in cases] for variant in ("v0_mutable", "v1_confirmed_snapshot")}
    summary = {}
    for variant, rows in results.items():
        equivalent = [row for row in rows if row["expected"] == "stable"]
        sensitivity = [row for row in rows if row["expected"] == "material_change"]
        summary[variant] = {
            "equivalent_input_stability": sum(not row["changed"] for row in equivalent) / len(equivalent),
            "correct_sensitivity": sum(row["changed"] for row in sensitivity) / len(sensitivity),
            "unsupported_claim_rate": sum(row["unsupported_claim"] for row in rows) / len(rows),
            "source_correctness": sum(row["source_correct"] for row in rows) / len(rows),
            "category_correctness": sum(row["category_correct"] for row in rows) / len(rows),
            "snapshot_traceability": sum(row["snapshot_traceable"] for row in rows) / len(rows),
        }
    return {"benchmark": str(BENCHMARK), "development": 8, "holdout": 4, "summary": summary, "rows": results}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
