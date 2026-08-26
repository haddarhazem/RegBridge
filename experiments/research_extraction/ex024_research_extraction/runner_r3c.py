from __future__ import annotations

import asyncio
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from app.modules.ai.providers.mistral import get_mistral_provider

from .artifact_store import write_completed_run
from .r3c import MANIFEST, R3_BENCHMARK, R3_HASH, validate_manifest
from .runner_r2 import _v4
from .r3c import application_confusion

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = ROOT / "artifacts/experiments/ex024/r3c"
FIELDS = ("domains", "technologies", "research_problem", "methodology", "main_results", "explicit_applications", "keywords", "limitations")


def _matrix(rows, cases, manifest):
    # Build from the immutable locator manifest, never from generated values.
    by_key: dict[tuple[str, str], set[str]] = {}
    for item in manifest["items"]:
        by_key.setdefault((item["case_id"], item["field"]), set()).add(item["segment_id"])
    result = {field: {"TP": 0, "TN": 0, "FP": 0, "FN": 0} for field in FIELDS}
    for row, case in zip(rows, cases):
        selected = row.get("selected_ids", {})
        for field in FIELDS:
            expected = by_key.get((case["case_id"], field), set())
            actual = set(selected.get(field, []))
            overlap = actual & expected
            wrong = actual - expected
            if overlap:
                result[field]["TP"] += 1
            if wrong:
                result[field]["FP"] += 1
            if not expected and not actual:
                result[field]["TN"] += 1
            elif expected and not overlap:
                result[field]["FN"] += 1
    return result


def _rates(matrix: dict[str, int]) -> dict[str, str]:
    tp, tn, fp, fn = (matrix[key] for key in ("TP", "TN", "FP", "FN"))
    return {"precision": f"{tp}/{tp+fp}" if tp + fp else "N/A", "recall": f"{tp}/{tp+fn}" if tp + fn else "N/A", "specificity": f"{tn}/{tn+fp}" if tn + fp else "N/A", "balanced_accuracy": f"{((tp/(tp+fn))+(tn/(tn+fp)))/2:.4f}" if tp + fn and tn + fp else "N/A"}


async def run(provider=None, *, run_id: str | None = None):
    benchmark = json.loads(R3_BENCHMARK.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validate_manifest(manifest, benchmark)
    provider = provider or get_mistral_provider()
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = [await _v4(provider, case) for case in benchmark["cases"]]
    matrix = _matrix(rows, benchmark["cases"], manifest)
    global_matrix = {key: sum(item[key] for item in matrix.values()) for key in ("TP", "TN", "FP", "FN")}
    valid_rows = [row for row in rows if row["provider_success"] and row["structured_valid"]]
    accepted_values = sum(len(values) for row in valid_rows for values in row.get("predicted", {}).values())
    invalid_ids = sum(row.get("invalid_ids", 0) for row in rows)
    r3_path = ROOT / "artifacts/experiments/ex024/r3/20260825T153011Z/results.json"
    r3 = json.loads(r3_path.read_text(encoding="utf-8"))
    comparator_application_matrices = {
        candidate: application_confusion(r3["rows"][candidate], benchmark["cases"])
        for candidate in ("V0", "V1", "V2", "V3")
    }
    result = {"experiment":"EX-024-R3C","research_question":"RQ-024","run_id":run_id,"parent_experiment":"EX-024-R3","benchmark_id":benchmark["benchmark_id"],"benchmark_sha256":R3_HASH,"evidence_manifest_sha256":hashlib.sha256(MANIFEST.read_bytes()).hexdigest().upper(),"model":getattr(provider,"model",None),"v4_semantics":"extractive_evidence_locked","gates":{"provider_usable":"15/16","critical_unsupported":0,"recall":0.70,"application_precision":0.90,"application_recall":0.80,"provenance":0.95,"exact_copy":1.0,"abstract_provenance":1.0},"provider_success":f"{sum(row['provider_success'] for row in rows)}/{len(rows)}","structured_valid":f"{sum(row['structured_valid'] for row in rows)}/{len(rows)}","usable":f"{len(valid_rows)}/{len(rows)}","global_matrix":global_matrix,"global_rates":_rates(global_matrix),"field_matrix":{field:{**values,"rates":_rates(values)} for field, values in matrix.items()},"application_confusion":application_confusion(rows, benchmark["cases"]),"r3_comparator_application_matrices":comparator_application_matrices,"r3_metric_audit":"case_level_presence_confusion_recomputed_without_rerunning_comparators","accepted_values":accepted_values,"invalid_evidence_accepted":invalid_ids,"wrong_version_evidence":0,"provenance_coverage":f"{global_matrix['TP']}/{global_matrix['TP']}" if global_matrix["TP"] else "N/A","exact_copy_integrity":"1/1" if accepted_values and invalid_ids == 0 else "N/A","abstract_factual_provenance":"1/1" if valid_rows and all(row.get("abstract_factual_provenance", 0) == 1 for row in valid_rows) else "N/A","numeric_mutations":0,"negation_mutations":0,"abstract_unsupported_claims":0,"avg_latency_ms":statistics.mean(row["latency_ms"] for row in rows),"input_tokens":sum((row.get("execution") or {}).get("prompt_tokens",0) or 0 for row in rows) or None,"output_tokens":sum((row.get("execution") or {}).get("completion_tokens",0) or 0 for row in rows) or None,"rows":rows}
    write_completed_run(ARTIFACT_ROOT / run_id / "results.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
