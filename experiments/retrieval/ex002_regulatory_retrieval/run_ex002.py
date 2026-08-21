"""Execute EX-002 dense retrieval without exposing Qdrant mutation methods."""

from __future__ import annotations

import json
import os
import platform
import statistics
import time
import uuid
from importlib.metadata import version
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from qdrant_client import QdrantClient

from .contracts import BenchmarkItem
from .embedder import BGEQueryEncoder
from .qdrant_reader import ReadOnlyQdrantReader


K_VALUES = (3, 5, 10)
PENDING_IDS = {"REG-004", "REG-007", "REG-021", "REG-022", "REG-025"}


def load_items(path: Path) -> list[BenchmarkItem]:
    return [
        BenchmarkItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate_benchmark(path: Path) -> tuple[list[BenchmarkItem], dict[str, Any]]:
    items = load_items(path)
    ids = [item.id for item in items]
    duplicates = sorted({item_id for item_id in ids if ids.count(item_id) > 1})
    validated = [item for item in items if item.annotation_status == "human_validated"]
    pending = [item for item in items if item.annotation_status == "needs_human_validation"]
    invalid_locators: list[str] = []
    for item in validated:
        for evidence in item.expected_evidence:
            if not evidence.point_id:
                invalid_locators.append(f"{item.id}:missing_point_id")
                continue
            try:
                uuid.UUID(evidence.point_id)
            except ValueError:
                invalid_locators.append(f"{item.id}:{evidence.point_id}")
    summary = {
        "total_questions": len(items),
        "human_validated": len(validated),
        "pending": len(pending),
        "pending_ids": sorted(item.id for item in pending),
        "duplicate_ids": duplicates,
        "jsonl_parse_errors": [],
        "human_validated_missing_expected_evidence": [
            item.id for item in validated if not item.expected_evidence
        ],
        "invalid_point_id_locators": invalid_locators,
    }
    if (
        summary["total_questions"] != 25
        or summary["human_validated"] != 20
        or summary["pending"] != 5
        or set(summary["pending_ids"]) != PENDING_IDS
        or duplicates
        or summary["human_validated_missing_expected_evidence"]
        or invalid_locators
    ):
        raise RuntimeError(f"Benchmark gate failed: {summary}")
    return validated, summary


def _vector_config(info: Any) -> tuple[int | None, str | None]:
    vectors = getattr(getattr(getattr(info, "config", None), "params", None), "vectors", None)
    if isinstance(vectors, dict):
        vectors = next(iter(vectors.values()), None)
    size = getattr(vectors, "size", None)
    distance = getattr(getattr(vectors, "distance", None), "value", None) or str(getattr(vectors, "distance", None))
    return size, distance


def collection_snapshot(reader: ReadOnlyQdrantReader) -> dict[str, Any]:
    info = reader.get_collection_info()
    size, distance = _vector_config(info)
    return {
        "collection": reader.collection,
        "points_count": reader.count(exact=True),
        "indexed_vectors_count": getattr(info, "indexed_vectors_count", None),
        "segments_count": getattr(info, "segments_count", None),
        "vector_size": size,
        "distance": distance,
    }


def _point_dict(point: Any) -> dict[str, Any]:
    return {
        "point_id": str(point.id),
        "score": float(point.score),
        "payload": point.payload or {},
    }


def _matched_ids(item: BenchmarkItem, points: list[dict[str, Any]]) -> set[str]:
    expected = {e.point_id for e in item.expected_evidence if e.point_id}
    return {point["point_id"] for point in points if point["point_id"] in expected}


def metric_row(item: BenchmarkItem, points: list[dict[str, Any]], k: int) -> dict[str, Any]:
    top = points[:k]
    expected = {e.point_id for e in item.expected_evidence if e.point_id}
    matched = _matched_ids(item, top)
    first_rank = next((rank for rank, point in enumerate(top, 1) if point["point_id"] in expected), None)
    return {
        "question_id": item.id,
        "difficulty": item.difficulty,
        "topic": item.topic,
        "k": k,
        "retrieved_point_ids": [point["point_id"] for point in top],
        "expected_point_ids": sorted(expected),
        "matched_point_ids": sorted(matched),
        "recall": len(matched) / len(expected),
        "precision": len(matched) / k,
        "mrr": 0.0 if first_rank is None else 1 / first_rank,
        "evidence_coverage": 1.0 if matched else 0.0,
        "first_relevant_rank": first_rank,
        "points": top,
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    low, high = int(index), min(int(index) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def latency_summary(values: list[float]) -> dict[str, float | int]:
    return {
        "median_ms": statistics.median(values) if values else 0.0,
        "p95_ms": percentile(values, 0.95),
        "sample_count": len(values),
    }


def main() -> None:
    benchmark_path = Path(os.getenv("EX002_BENCHMARK", "benchmarks/regulatory_retrieval_v1.jsonl"))
    artifact_dir = Path(os.getenv("EX002_ARTIFACT_DIR", "artifacts/experiments/EX-002"))
    config = dotenv_values(".env")
    qdrant_url = config.get("QDRANT_URL") or os.getenv("QDRANT_URL")
    api_key = config.get("QDRANT_API_KEY") or os.getenv("QDRANT_API_KEY")
    collection = config.get("QDRANT_COLLECTION") or os.getenv("QDRANT_COLLECTION", "reglementation_chunks")
    if not qdrant_url or not api_key:
        raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be configured in .env or the environment")

    items, benchmark_summary = validate_benchmark(benchmark_path)
    client = QdrantClient(url=qdrant_url, api_key=api_key, timeout=60)
    reader = ReadOnlyQdrantReader(client, collection)
    start_snapshot = collection_snapshot(reader)
    encoder = BGEQueryEncoder(
        model_name=os.getenv("BGE_M3_MODEL_NAME", config.get("BGE_M3_MODEL_NAME", "BAAI/bge-m3")),
        device=os.getenv("BGE_M3_DEVICE", config.get("BGE_M3_DEVICE", "cpu")),
    )

    # Warm up model and one Qdrant query before recording final samples.
    warm_vector = encoder.encode(items[0].question)
    if len(warm_vector) != 1024:
        raise RuntimeError(f"Query vector dimension is {len(warm_vector)}, expected 1024")
    reader.search(warm_vector, limit=10)

    runs: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    embedding_ms: list[float] = []
    qdrant_ms: dict[str, list[float]] = {str(k): [] for k in K_VALUES}
    combined_ms: dict[str, list[float]] = {str(k): [] for k in K_VALUES}
    for item in items:
        embedding_start = time.perf_counter_ns()
        vector = encoder.encode(item.question)
        embedding_duration = (time.perf_counter_ns() - embedding_start) / 1_000_000
        if len(vector) != 1024:
            raise RuntimeError(f"Query vector dimension is {len(vector)}, expected 1024")
        embedding_ms.append(embedding_duration)
        for k in K_VALUES:
            retrieval_start = time.perf_counter_ns()
            points = [_point_dict(point) for point in reader.search(vector, limit=k)]
            retrieval_duration = (time.perf_counter_ns() - retrieval_start) / 1_000_000
            qdrant_ms[str(k)].append(retrieval_duration)
            combined_ms[str(k)].append(embedding_duration + retrieval_duration)
            metric_rows.append(metric_row(item, points, k))
            runs.append({
                "question_id": item.id,
                "question": item.question,
                "k": k,
                "points": points,
                "embedding_latency_ms": embedding_duration,
                "qdrant_latency_ms": retrieval_duration,
                "combined_latency_ms": embedding_duration + retrieval_duration,
            })

    end_snapshot = collection_snapshot(reader)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "retrieval_runs.jsonl").write_text(
        "".join(json.dumps(run, ensure_ascii=False) + "\n" for run in runs), encoding="utf-8"
    )
    metrics: dict[str, Any] = {
        "benchmark": benchmark_summary,
        "configurations": {},
        "per_question": metric_rows,
    }
    for k in K_VALUES:
        rows = [row for row in metric_rows if row["k"] == k]
        metrics["configurations"][str(k)] = {
            "recall": statistics.mean(row["recall"] for row in rows),
            "precision": statistics.mean(row["precision"] for row in rows),
            "mrr": statistics.mean(row["mrr"] for row in rows),
            "evidence_coverage": statistics.mean(row["evidence_coverage"] for row in rows),
        }
    (artifact_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latency = {
        "embedding": latency_summary(embedding_ms),
        "qdrant": {str(k): latency_summary(qdrant_ms[str(k)]) for k in K_VALUES},
        "combined": {str(k): latency_summary(combined_ms[str(k)]) for k in K_VALUES},
    }
    (artifact_dir / "latency.json").write_text(json.dumps(latency, indent=2) + "\n", encoding="utf-8")
    metadata = {
        "benchmark_path": str(benchmark_path),
        "collection_start": start_snapshot,
        "collection_end": end_snapshot,
        "collection_changed": start_snapshot != end_snapshot,
        "embedding_model": os.getenv("BGE_M3_MODEL_NAME", config.get("BGE_M3_MODEL_NAME", "BAAI/bge-m3")),
        "device": os.getenv("BGE_M3_DEVICE", config.get("BGE_M3_DEVICE", "cpu")),
        "query_vector_dimension": len(warm_vector),
        "python_version": platform.python_version(),
        "qdrant_client_version": version("qdrant-client"),
        "platform": platform.platform(),
        "git_commit": os.popen("git rev-parse HEAD").read().strip(),
        "qdrant_mutation_operations_executed": [],
        "historical_embedding_parity_proven": False,
    }
    (artifact_dir / "metadata_audit.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"benchmark": benchmark_summary, "start": start_snapshot, "end": end_snapshot, "metrics": metrics["configurations"], "latency": latency}, indent=2))


if __name__ == "__main__":
    main()
