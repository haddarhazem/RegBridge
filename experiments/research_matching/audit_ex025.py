from __future__ import annotations

import json
import math
import random
from pathlib import Path

from .matcher import rank, relevance

ROOT = Path(__file__).parents[2]


def _query_values(benchmark: dict, candidate: str, need_id: str, k: int) -> dict:
    need = next(row for row in benchmark["needs"] if row["id"] == need_id)
    corpus = benchmark["research_snapshots"]
    ranked = rank(need, corpus, candidate)
    gains = [relevance(benchmark, need_id, row["id"]) for row in ranked]
    relevant = sum(gain > 0 for gain in gains)
    top = gains[:k]
    rprecision = sum(gain > 0 for gain in gains[:relevant]) / relevant if relevant else None
    precisions = [sum(gain > 0 for gain in gains[:index]) / index for index, gain in enumerate(gains, 1) if gain > 0]
    average_precision = sum(precisions) / relevant if relevant else None
    dcg = sum((2 ** gain - 1) / math.log2(index + 2) for index, gain in enumerate(top))
    ideal = sorted(gains, reverse=True)[:k]
    idcg = sum((2 ** gain - 1) / math.log2(index + 2) for index, gain in enumerate(ideal))
    first_strong = next((index + 1 for index, gain in enumerate(gains) if gain == 2), None)
    retrieved_relevant = sum(gain > 0 for gain in top)
    recall = retrieved_relevant / relevant if relevant else None
    return {"relevant": relevant, "strong": sum(gain == 2 for gain in gains), "partial": sum(gain == 1 for gain in gains), "not_relevant": sum(gain == 0 for gain in gains), "precision": retrieved_relevant / k, "recall": recall, "mrr": 1 / first_strong if first_strong else 0.0, "ndcg": dcg / idcg if idcg else 1.0, "oracle_precision": min(relevant, k) / k, "oracle_recall": 1.0 if relevant else None, "oracle_mrr": 1.0 if first_strong else 0.0, "oracle_ndcg": 1.0, "rprecision": rprecision, "map": average_precision}


def _mean(values: list[float | None]) -> float | None:
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def canonical_metrics(benchmark: dict, candidate: str, need_ids: list[str]) -> dict:
    positive = [need_id for need_id in need_ids if need_id not in benchmark["zero_relevant_need_ids"]]
    rows = [_query_values(benchmark, candidate, need_id, 5) for need_id in positive]
    return {"P@5": _mean([row["precision"] for row in rows]), "Recall@5": _mean([row["recall"] for row in rows]), "MRR": _mean([row["mrr"] for row in rows]), "nDCG@5": _mean([row["ndcg"] for row in rows]), "R-Precision": _mean([row["rprecision"] for row in rows]), "MAP": _mean([row["map"] for row in rows]), "positive_queries": len(positive), "zero_match_queries": len(need_ids) - len(positive)}


def main() -> None:
    path = ROOT / "benchmarks/research_matching_ex025_v1.json"
    benchmark = json.loads(path.read_text(encoding="utf-8"))
    all_ids = benchmark["development_need_ids"] + benchmark["holdout_need_ids"]
    distributions = {need_id: _query_values(benchmark, "V0", need_id, 5) for need_id in all_ids}
    holdout = benchmark["holdout_need_ids"]
    oracle = {f"P@{k}": _mean([_query_values(benchmark, "V0", need_id, k)["oracle_precision"] for need_id in holdout]) for k in (1, 3, 5, 10)}
    oracle.update({"Recall@5": _mean([distributions[need_id]["oracle_recall"] for need_id in holdout]), "MRR": _mean([distributions[need_id]["oracle_mrr"] for need_id in holdout]), "nDCG@5": _mean([distributions[need_id]["oracle_ndcg"] for need_id in holdout])})
    rows = {candidate: {need_id: _query_values(benchmark, candidate, need_id, 5) for need_id in holdout} for candidate in ("V0", "V1")}
    bootstrap = {}
    rng = random.Random(211)
    for candidate, candidate_rows in rows.items():
        samples = {key: [] for key in ("ndcg", "recall", "mrr", "rprecision", "map")}
        for _ in range(1000):
            draw = [candidate_rows[rng.choice(holdout)] for _ in holdout]
            for key in samples:
                samples[key].append(_mean([row[key] for row in draw]))
        bootstrap[candidate] = {key: {"point": _mean([row[key] for row in candidate_rows.values()]), "ci95": [sorted(values)[25], sorted(values)[974]]} for key, values in samples.items()}
    result = {"experiment": "EX-025-audit", "original_benchmark_sha256": "b6d47b0714d475c4507c5e9b330340e7c9f38b5562c4c88d4946876598dcdbaf", "binary_relevance": "STRONG + PARTIAL", "zero_match_ids": benchmark["zero_relevant_need_ids"], "distributions": distributions, "oracle": oracle, "canonical_positive_aggregates": {candidate: canonical_metrics(benchmark, candidate, benchmark["holdout_need_ids"]) for candidate in ("V0", "V1")}, "original_p5_gate": {"threshold": 0.70, "oracle_p5": oracle["P@5"], "classification": "INAPPROPRIATE" if oracle["P@5"] < 0.70 else "ACHIEVABLE"}, "bootstrap_1000_seed_211": bootstrap, "variable_length_denominator": "fixed k; current ranker always evaluates a full corpus and slices top k", "r_precision": "added for R1", "map": "added for R1"}
    out = ROOT / "artifacts/experiments/ex025_metric_audit.json"; out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8"); print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
