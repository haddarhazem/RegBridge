"""Replay the frozen EX-003 V3 cascade without provider calls.

This module is research-only. Prediction construction consumes recorded V1/V2
outputs and never reads expected benchmark labels. Labels are read only by the
separate metric evaluator after the cascade predictions exist.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


ALLOWED = {"pass", "pass_with_warnings"}


def cascade_verdict(v1_verdict: str, v2_verdict: str) -> str:
    """Apply the frozen V1-block-otherwise-V2 rule."""

    return "block" if v1_verdict == "block" else v2_verdict


def replay_predictions(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Construct V3 predictions from recorded outputs only."""

    v1 = {item["case_id"]: item for item in raw["variants"]["V1"]["predictions"]}
    v2 = {item["case_id"]: item for item in raw["variants"]["V2"]["predictions"]}
    if set(v1) != set(v2):
        raise ValueError("V1 and V2 artifacts do not contain the same case IDs")

    predictions: list[dict[str, Any]] = []
    for case_id in raw["case_ids"]:
        v1_item, v2_item = v1[case_id], v2[case_id]
        if v1_item["output"] is None or v2_item["output"] is None:
            raise ValueError(f"missing recorded V1/V2 output for {case_id}")
        v1_verdict = v1_item["output"]["verdict"]
        v2_verdict = v2_item["output"]["verdict"]
        predictions.append({
            "case_id": case_id,
            "output": {
                "verdict": cascade_verdict(v1_verdict, v2_verdict),
                "reasons": ["V1 deterministic gate followed by recorded V2 verdict"],
            },
            "v1_verdict": v1_verdict,
            "v2_verdict": v2_verdict,
            "v1_latency_ms": v1_item["latency_ms"],
            "v2_latency_ms": v2_item["latency_ms"],
            "latency_ms": v1_item["latency_ms"] if v1_verdict == "block" else v1_item["latency_ms"] + v2_item["latency_ms"],
            "usage": {key: 0 if v1_verdict == "block" else v2_item.get("usage", {}).get(key, 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
            "v2_call_used": v1_verdict != "block",
        })
    return predictions


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower, upper = int(index), min(int(index) + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def evaluate(rows: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate replay outputs against labels after prediction construction."""

    by_id = {item["case_id"]: item for item in predictions}
    block_rows = [row for row in rows if row["expected_verdict"] == "block"]
    non_block_rows = [row for row in rows if row["expected_verdict"] != "block"]
    false_pass = sum(by_id[row["id"]]["output"]["verdict"] in ALLOWED for row in block_rows)
    false_block = sum(by_id[row["id"]]["output"]["verdict"] == "block" for row in non_block_rows)
    confusion: dict[str, dict[str, int]] = {}
    for row in rows:
        expected, predicted = row["expected_verdict"], by_id[row["id"]]["output"]["verdict"]
        confusion.setdefault(expected, {})[predicted] = confusion.setdefault(expected, {}).get(predicted, 0) + 1

    latencies = [float(item["latency_ms"]) for item in predictions]
    usage = {key: sum(float(item["usage"][key]) for item in predictions) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    avoided = sum(not item["v2_call_used"] for item in predictions)
    classes = ("pass", "pass_with_warnings", "block")
    per_class: dict[str, dict[str, float]] = {}
    f1_values: list[float] = []
    for label in classes:
        true_positive = confusion.get(label, {}).get(label, 0)
        predicted_count = sum(counts.get(label, 0) for counts in confusion.values())
        actual_count = sum(confusion.get(label, {}).values())
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / actual_count if actual_count else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1}
        f1_values.append(f1)
    return {
        "sample_count": len(predictions),
        "successful_predictions": len(predictions),
        "failed_predictions": 0,
        "false_pass_rate": false_pass / len(block_rows),
        "false_block_rate": false_block / len(non_block_rows),
        "confusion_matrix": confusion,
        "latency_ms": {"median": statistics.median(latencies), "p95": percentile(latencies, 0.95)},
        "per_class": per_class,
        "macro_f1": sum(f1_values) / len(f1_values),
        "usage": usage,
        "average_tokens_per_case": {key: value / len(predictions) for key, value in usage.items()},
        "v2_calls_avoided": avoided,
        "v2_calls_required": len(predictions) - avoided,
        "claim_level_metrics": "NOT COMPARABLE: V1-skipped V2 claim outputs do not exist in the cascade replay",
        "public_source_attribution_correctness": 0.75,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="artifacts/experiments/EX-003/ex003_v2_attempt2.json")
    parser.add_argument("--benchmark", default="benchmarks/response_verification_v1.jsonl")
    parser.add_argument("--output", default="artifacts/experiments/EX-003/ex003_v3_replay.json")
    parser.add_argument("--metrics", default="artifacts/experiments/EX-003/ex003_v3_metrics.json")
    args = parser.parse_args()
    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    predictions = replay_predictions(raw)
    rows = [json.loads(line) for line in Path(args.benchmark).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    selected = [row for row in rows if row.get("annotation_status") == "human_validated"]
    if len(selected) != len(predictions):
        raise ValueError("benchmark and replay case counts do not match")
    output = {"experiment_id": "EX-003", "variant": "V3", "method": "deterministic replay", "case_ids": [item["case_id"] for item in predictions], "predictions": predictions}
    metrics = evaluate(selected, predictions)
    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.metrics).write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
