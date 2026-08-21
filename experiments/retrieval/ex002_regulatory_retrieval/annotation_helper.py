from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import dotenv_values
from qdrant_client import QdrantClient

from .contracts import BenchmarkItem, CandidateEvidence
from .embedder import BGEQueryEncoder
from .qdrant_reader import ReadOnlyQdrantReader


def load_items(path: Path) -> list[BenchmarkItem]:
    text = path.read_text(encoding="utf-8").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [BenchmarkItem.model_validate_json(line) for line in text.splitlines() if line.strip()]
    if isinstance(parsed, dict):
        parsed = [parsed]
    return [BenchmarkItem.model_validate(item) for item in parsed]


def retrieve_candidates(items: list[BenchmarkItem], reader: ReadOnlyQdrantReader, encoder: BGEQueryEncoder, limit: int) -> list[CandidateEvidence]:
    candidates: list[CandidateEvidence] = []
    for item in items:
        points = reader.search(encoder.encode(item.question), limit=limit)
        for rank, point in enumerate(points, start=1):
            payload = point.payload or {}
            candidates.append(CandidateEvidence(
                question_id=item.id,
                question=item.question,
                rank=rank,
                point_id=str(point.id),
                score=float(point.score),
                source_domain=payload.get("source_domain"),
                url=payload.get("url"),
                parent_url=payload.get("parent_url"),
                chunk_index=payload.get("chunk_index"),
                content_excerpt=str(payload.get("content", ""))[:500].replace("\n", " "),
            ))
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only EX-002 Qdrant annotation worksheet generator")
    parser.add_argument("--benchmark", type=Path, default=Path("benchmarks/regulatory_retrieval_v1.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/experiments/EX-002/annotation_candidates.jsonl"))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--pending-only", action="store_true")
    args = parser.parse_args()
    config = dotenv_values(".env")
    reader = ReadOnlyQdrantReader(QdrantClient(url=config["QDRANT_URL"], api_key=config["QDRANT_API_KEY"], timeout=30), config["QDRANT_COLLECTION"])
    items = load_items(args.benchmark)
    if args.pending_only:
        items = [item for item in items if item.annotation_status != "human_validated"]
    encoder = BGEQueryEncoder(model_name=os.getenv("BGE_M3_MODEL_NAME", config.get("BGE_M3_MODEL_NAME", "BAAI/bge-m3")), device=os.getenv("BGE_M3_DEVICE", config.get("BGE_M3_DEVICE", "cpu")))
    candidates = retrieve_candidates(items, reader, encoder, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(item.model_dump_json() for item in candidates) + "\n", encoding="utf-8")
    print(f"Wrote {len(candidates)} candidates for human annotation to {args.output}")
