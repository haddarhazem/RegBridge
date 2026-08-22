"""Untouched final validation set for EX-006; V1 is not tuned here."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.assessment_stability.ex006_assessment_stability.run_ex006 import evaluate


BENCHMARK = Path(__file__).resolve().parents[3] / "benchmarks" / "regulatory_assessment_stability_final_v1.json"


def run_final_validation() -> dict:
    cases = json.loads(BENCHMARK.read_text(encoding="utf-8"))["scenarios"]
    rows = [evaluate(case, "v1_confirmed_snapshot") for case in cases]
    stable = [row for row in rows if row["expected"] == "stable"]
    changed = [row for row in rows if row["expected"] == "material_change"]
    return {
        "cases": len(rows),
        "equivalent_input_stability": sum(not row["changed"] for row in stable) / len(stable),
        "correct_sensitivity": sum(row["changed"] for row in changed) / len(changed),
        "unsupported_claim_rate": sum(row["unsupported_claim"] for row in rows) / len(rows),
        "source_correctness": sum(row["source_correct"] for row in rows) / len(rows),
        "category_correctness": sum(row["category_correct"] for row in rows) / len(rows),
        "snapshot_traceability": sum(row["snapshot_traceable"] for row in rows) / len(rows),
        "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(run_final_validation(), ensure_ascii=False, indent=2))
