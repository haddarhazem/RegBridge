"""Evaluate one reranker on the fixed EX-002 dense top-10 candidate pool."""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path

import torch
from dotenv import dotenv_values
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from .contracts import BenchmarkItem
from .run_ex002 import K_VALUES, latency_summary, metric_row


MODEL_NAME = "BAAI/bge-reranker-v2-m3"


def main() -> None:
    base = Path(os.getenv("EX002_ARTIFACT_DIR", "artifacts/experiments/EX-002"))
    benchmark = Path(os.getenv("EX002_BENCHMARK", "benchmarks/regulatory_retrieval_v1.jsonl"))
    config = dotenv_values(".env")
    device = os.getenv("BGE_M3_DEVICE", config.get("BGE_M3_DEVICE", "cpu"))
    max_length = int(os.getenv("EX002_RERANK_MAX_LENGTH", "512"))
    items = {
        item.id: item
        for item in (BenchmarkItem.model_validate_json(line) for line in benchmark.read_text(encoding="utf-8").splitlines() if line.strip())
        if item.annotation_status == "human_validated"
    }
    dense_runs = {
        run["question_id"]: run
        for run in (json.loads(line) for line in (base / "retrieval_runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())
        if run["k"] == 10
    }
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME).to(device).eval()

    # Warm up the reranker before recording final timings.
    first_id = next(iter(dense_runs))
    first = dense_runs[first_id]
    warm = tokenizer([items[first_id].question], [p["payload"].get("content", "") for p in first["points"]], padding=True, truncation=True, max_length=max_length, return_tensors="pt").to(device)
    with torch.inference_mode():
        model(**warm).logits

    reranked: dict[str, list[dict]] = {}
    rerank_ms: list[float] = []
    for question_id, run in dense_runs.items():
        question = items[question_id].question
        points = run["points"]
        batch = tokenizer([question] * len(points), [p["payload"].get("content", "") for p in points], padding=True, truncation=True, max_length=max_length, return_tensors="pt").to(device)
        started = time.perf_counter_ns()
        with torch.inference_mode():
            scores = model(**batch).logits.reshape(-1).float().cpu().tolist()
        duration = (time.perf_counter_ns() - started) / 1_000_000
        rerank_ms.append(duration)
        ordered = []
        for point, score in zip(points, scores, strict=True):
            copy = dict(point)
            copy["reranker_score"] = float(score)
            ordered.append(copy)
        reranked[question_id] = sorted(ordered, key=lambda point: point["reranker_score"], reverse=True)

    rows = []
    for k in K_VALUES:
        rows.extend(metric_row(items[qid], points, k) for qid, points in reranked.items())
    metrics = {str(k): {
        "recall": statistics.mean(row["recall"] for row in rows if row["k"] == k),
        "precision": statistics.mean(row["precision"] for row in rows if row["k"] == k),
        "mrr": statistics.mean(row["mrr"] for row in rows if row["k"] == k),
        "evidence_coverage": statistics.mean(row["evidence_coverage"] for row in rows if row["k"] == k),
    } for k in K_VALUES}
    (base / "reranked_runs.jsonl").write_text(
        "".join(json.dumps({"question_id": qid, "k": 10, "points": points}, ensure_ascii=False) + "\n" for qid, points in reranked.items()),
        encoding="utf-8",
    )
    (base / "reranking_metrics.json").write_text(json.dumps({"model": MODEL_NAME, "candidate_pool": "dense_top_10", "max_length": max_length, "metrics": metrics, "per_question": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latency = latency_summary(rerank_ms)
    (base / "reranking_latency.json").write_text(json.dumps({"model": MODEL_NAME, "latency": latency, "sample_count": len(rerank_ms)}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model": MODEL_NAME, "candidate_pool": "fixed dense top-10", "max_length": max_length, "metrics": metrics, "latency": latency}, indent=2))


if __name__ == "__main__":
    main()
