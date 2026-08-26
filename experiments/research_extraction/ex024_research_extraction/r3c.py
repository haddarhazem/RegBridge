from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.modules.research.extraction_parser import parse_source, segment_source, resolve_segment

from .artifact_store import write_completed_run

ROOT = Path(__file__).resolve().parents[3]
R3_BENCHMARK = ROOT / "benchmarks/research_extraction_ex024_r3_holdout_v1.json"
R3_HASH = "7844F7AD2A2FC5A9883FAD873C7252B60B1E61B18E1EE09760F4E70F60220A17"
MANIFEST = ROOT / "benchmarks/research_extraction_ex024_r3_gold_evidence_manifest_v1.json"


def build_manifest(benchmark: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for case in benchmark["cases"]:
        parsed = parse_source(case["case_id"], "text/plain", case["source_text"].encode())
        segments = segment_source(parsed)
        source_hash = hashlib.sha256(case["source_text"].encode()).hexdigest()
        for field, values in case["gold"].items():
            for ordinal, value in enumerate(values):
                segment = next((candidate for candidate in segments if candidate.text == value), None)
                if segment is None:
                    raise ValueError(f"gold value has no exact deterministic segment: {case['case_id']}:{field}")
                items.append({"case_id": case["case_id"], "field": field, "ordinal": ordinal, "expected_status": "SUPPORTED", "canonical_value": value, "source_version_id": case["case_id"], "source_sha256": source_hash, "segment_id": segment.segment_id, "locator": segment.locator.__dict__, "critical": field in {"technologies", "main_results", "explicit_applications"}})
    return {"manifest_id":"research-extraction-ex024-r3-gold-evidence-v1","benchmark_id":benchmark["benchmark_id"],"original_benchmark_sha256":R3_HASH,"statuses_changed":False,"canonical_values_changed":False,"items":items}


def validate_manifest(manifest: dict[str, Any], benchmark: dict[str, Any]) -> None:
    if len(manifest["items"]) != 64:
        raise ValueError("expected 64 supported gold evidence items")
    for item in manifest["items"]:
        case = next(case for case in benchmark["cases"] if case["case_id"] == item["case_id"])
        parsed = parse_source(item["source_version_id"], "text/plain", case["source_text"].encode())
        segment = resolve_segment(segment_source(parsed), item["segment_id"], item["source_version_id"])
        if segment.text != item["canonical_value"] or hashlib.sha256(case["source_text"].encode()).hexdigest() != item["source_sha256"]:
            raise ValueError(f"invalid frozen evidence manifest item: {item['case_id']}:{item['field']}")


def materialize_manifest() -> dict[str, Any]:
    benchmark = json.loads(R3_BENCHMARK.read_text(encoding="utf-8"))
    manifest = build_manifest(benchmark)
    validate_manifest(manifest, benchmark)
    write_completed_run(MANIFEST, manifest)
    return manifest


def application_confusion(rows: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, int]:
    result = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}
    for row, case in zip(rows, cases):
        gold = bool(case["gold"].get("explicit_applications", []))
        predicted = bool((row.get("predicted") or {}).get("explicit_applications", []))
        if gold and predicted:
            result["TP"] += 1
        elif not gold and not predicted:
            result["TN"] += 1
        elif predicted:
            result["FP"] += 1
        else:
            result["FN"] += 1
    return result
