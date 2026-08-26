from __future__ import annotations

import math
import re
from collections import Counter

CORE = ("domains", "technologies", "research_problem", "keywords")


def tokens(value: object) -> set[str]:
    if value is None:
        return set()
    text = " ".join(str(item) for item in value) if isinstance(value, list) else str(value)
    return {item for item in re.findall(r"[\w-]+", text.casefold()) if len(item) > 1}


def structured(need: dict, research: dict) -> tuple[float, list[dict]]:
    scores: list[float] = []
    reasons: list[dict] = []
    for field in CORE:
        left, right = tokens(need.get(field)), tokens(research.get(field))
        if not left or not right:
            continue
        overlap = left & right
        score = len(overlap) / len(left | right)
        scores.append(score)
        if overlap:
            reasons.append({"code": "FIELD_OVERLAP", "startup_field": field, "research_field": field, "terms": sorted(overlap)})
    return (sum(scores) / len(scores) if scores else 0.0), reasons


def canonical(item: dict) -> str:
    return " ".join(f"{field}: {' '.join(str(v) for v in item.get(field, []))}" for field in CORE)


def sparse(need: dict, research: dict, corpus: list[dict]) -> float:
    query = tokens(canonical(need))
    docs = [tokens(canonical(item)) for item in corpus]
    if not query:
        return 0.0
    avgdl = sum(len(doc) for doc in docs) / max(1, len(docs))
    doc = tokens(canonical(research)); dl = len(doc); score = 0.0
    for term in query:
        tf = sum(1 for value in doc if value == term)
        if not tf:
            continue
        df = sum(term in value for value in docs)
        idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
        score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * dl / max(1, avgdl)))
    return score


def rank(need: dict, corpus: list[dict], candidate: str) -> list[dict]:
    rows = []
    for index, item in enumerate(corpus):
        if candidate == "V0":
            score, reasons = structured(need, item)
        elif candidate == "V1":
            score, reasons = sparse(need, item, corpus), []
        else:
            raise ValueError(f"unsupported candidate: {candidate}")
        rows.append({"id": item["id"], "score": score, "reasons": reasons, "tie": index})
    return sorted(rows, key=lambda row: (-row["score"], row["id"]))


def relevance(benchmark: dict, need_id: str, research_id: str) -> int:
    if research_id in benchmark.get("strong_pairs", {}).get(need_id, []):
        return 2
    if research_id in benchmark.get("partial_pairs", {}).get(need_id, []):
        return 1
    return 0


def metrics(benchmark: dict, candidate: str, need_ids: list[str], k: int = 5) -> dict:
    needs = {row["id"]: row for row in benchmark["needs"]}
    corpus = benchmark["research_snapshots"]
    precisions, recalls, hits, reciprocal, ndcgs = [], [], [], [], []
    for need_id in need_ids:
        ranked = rank(needs[need_id], corpus, candidate)[:k]
        relevant = {row["id"] for row in corpus if relevance(benchmark, need_id, row["id"]) > 0}
        strong = {row["id"] for row in corpus if relevance(benchmark, need_id, row["id"]) == 2}
        returned = [row["id"] for row in ranked]
        precisions.append(sum(relevance(benchmark, need_id, row["id"]) > 0 for row in ranked) / k)
        recalls.append(sum(item in relevant for item in returned) / len(relevant) if relevant else 1.0)
        hits.append(1.0 if any(item in relevant for item in returned) else 0.0)
        first = next((index + 1 for index, item in enumerate(returned) if item in strong), None)
        reciprocal.append(1 / first if first else 0.0)
        gains = [relevance(benchmark, need_id, item) for item in returned]
        dcg = sum((2 ** gain - 1) / math.log2(index + 2) for index, gain in enumerate(gains))
        ideal = sorted([relevance(benchmark, need_id, row["id"]) for row in corpus], reverse=True)[:k]
        idcg = sum((2 ** gain - 1) / math.log2(index + 2) for index, gain in enumerate(ideal))
        ndcgs.append(dcg / idcg if idcg else 1.0)
    return {f"P@{k}": sum(precisions) / len(precisions), f"R@{k}": sum(recalls) / len(recalls), f"HitRate@{k}": sum(hits) / len(hits), "MRR": sum(reciprocal) / len(reciprocal), f"nDCG@{k}": sum(ndcgs) / len(ndcgs)}
