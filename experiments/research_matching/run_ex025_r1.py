from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

import torch
from experiments.research_matching.matcher import rank, relevance, structured, sparse, tokens, canonical
from experiments.retrieval.ex002_regulatory_retrieval.embedder import BGEQueryEncoder

ROOT = Path(__file__).parents[2]
BENCH = ROOT / "benchmarks/research_matching_ex025_r1.json"


FIELDS = ("domains", "technologies", "research_problem", "keywords")


def encode_many(encoder, texts):
    unique = list(dict.fromkeys(texts))
    batch = encoder.tokenizer(unique, padding=True, truncation=True, return_tensors="pt").to(encoder.device)
    with torch.inference_mode():
        output = encoder.model(**batch).last_hidden_state
    mask = batch["attention_mask"].unsqueeze(-1).expand(output.size()).float()
    pooled = (output * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
    vectors = torch.nn.functional.normalize(pooled, p=2, dim=1).cpu().tolist()
    return dict(zip(unique, vectors))


def dense_rank(need, corpus, query_vectors, vectors):
    q = query_vectors[canonical(need)]
    rows = []
    for item in corpus:
        score = sum(a * b for a, b in zip(q, vectors[item["id"]]))
        rows.append({"id": item["id"], "score": score, "reasons": [], "tie": len(rows) + 1})
    return sorted(rows, key=lambda row: (-row["score"], row["id"]))


def field_dense_rank(need, corpus, query_field_vectors, field_vectors):
    rows = []
    for item in corpus:
        scores = []
        for field in FIELDS:
            if need.get(field) and item.get(field):
                q = query_field_vectors[str(need[field])]
                scores.append(sum(a * b for a, b in zip(q, field_vectors[item["id"]][field])))
        rows.append({"id": item["id"], "score": sum(scores) / len(scores) if scores else 0.0, "reasons": [], "tie": len(rows) + 1})
    return sorted(rows, key=lambda row: (-row["score"], row["id"]))


def hybrid_rank(need, corpus, candidate, structured_rows, dense, sparse_rows):
    d = {r["id"]: r for r in dense}
    s = {r["id"]: r for r in sparse_rows}
    if candidate == "V3":
        rows = [{"id": x["id"], "score": d[x["id"]]["score"], "reasons": [], "tie": x["id"]} for x in corpus]
    elif candidate == "V4":
        component_rankings = [structured_rows, sparse_rows, dense]
        positions = [{row["id"]: index + 1 for index, row in enumerate(component)} for component in component_rankings]
        rows = [{"id": x["id"], "score": sum(1 / (60 + position[x["id"]]) for position in positions), "reasons": [], "tie": x["id"]} for x in corpus]
    else:
        component_rows = [structured_rows, sparse_rows, dense]
        normalized = []
        for component in component_rows:
            scores = [row["score"] for row in component]
            low, high = min(scores), max(scores)
            normalized.append({row["id"]: (row["score"] - low) / (high - low) if high > low else 0.0 for row in component})
        rows = [{"id": x["id"], "score": sum(values[x["id"]] for values in normalized) / 3, "reasons": [], "tie": x["id"]} for x in corpus]
    return sorted(rows, key=lambda row: (-row["score"], row["id"]))


def values(bench, ranked, qid, k=5):
    relevant = {x for x in bench.get("strong_pairs", {}).get(qid, []) + bench.get("partial_pairs", {}).get(qid, [])}
    strong = set(bench.get("strong_pairs", {}).get(qid, []))
    top = [r["id"] for r in ranked[:k]]
    gains = [2 if x in strong else 1 if x in relevant else 0 for x in top]
    ideal = sorted([2] * len(strong) + [1] * (len(relevant - strong)), reverse=True)[:k]
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    first = next((i + 1 for i, x in enumerate(top) if x in strong), None)
    return {"precision": sum(x in relevant for x in top) / k, "recall": sum(x in relevant for x in top) / len(relevant) if relevant else 1.0, "mrr": 1 / first if first else 0.0, "ndcg": dcg / idcg if idcg else 1.0, "zero_match": not relevant}


def metric(bench, rankings, ids):
    rows = [values(bench, rankings[q], q) for q in ids]
    positive = [r for r in rows if not r["zero_match"]]
    return {"P@5_positive": sum(r["precision"] for r in positive) / len(positive), "Recall@5_positive": sum(r["recall"] for r in positive) / len(positive), "MRR_positive": sum(r["mrr"] for r in positive) / len(positive), "nDCG@5_positive": sum(r["ndcg"] for r in positive) / len(positive), "zero_match_count": sum(r["zero_match"] for r in rows), "queries": len(rows)}


def main():
    bench = json.loads(BENCH.read_text(encoding="utf-8"))
    raw = BENCH.read_bytes()
    needs = {x["id"]: x for x in bench["needs"]}
    corpus = bench["research_snapshots"]
    load_started = time.perf_counter()
    encoder = BGEQueryEncoder(device="cpu")
    cold_load_ms = (time.perf_counter() - load_started) * 1000
    texts = [canonical(x) for x in bench["needs"] + corpus]
    field_texts = [str(x[field]) for x in bench["needs"] + corpus for field in FIELDS if x.get(field)]
    started = time.perf_counter()
    encoded = encode_many(encoder, texts + field_texts)
    enc_ms = (time.perf_counter() - started) * 1000
    vectors = {x["id"]: encoded[canonical(x)] for x in corpus}
    query_vectors = {canonical(x): encoded[canonical(x)] for x in bench["needs"]}
    field_vectors = {x["id"]: {field: encoded[str(x[field])] for field in FIELDS if x.get(field)} for x in corpus}
    query_field_vectors = {str(x[field]): encoded[str(x[field])] for x in bench["needs"] for field in FIELDS if x.get(field)}
    rankings = {c: {} for c in ("V0", "V1", "V2", "V3", "V4", "V5")}
    for qid, need in needs.items():
        sparse_rows = rank(need, corpus, "V1")
        structured_rows = rank(need, corpus, "V0")
        dense_rows = dense_rank(need, corpus, query_vectors, vectors)
        field_rows = field_dense_rank(need, corpus, query_field_vectors, field_vectors)
        rankings["V0"][qid] = structured_rows
        rankings["V1"][qid] = sparse_rows
        rankings["V2"][qid] = dense_rows
        rankings["V3"][qid] = field_rows
        rankings["V4"][qid] = hybrid_rank(need, corpus, "V4", structured_rows, field_rows, sparse_rows)
        rankings["V5"][qid] = hybrid_rank(need, corpus, "V5", structured_rows, field_rows, sparse_rows)
    result = {"experiment":"EX-025-R1-corrected-instrumentation", "benchmark_sha256":hashlib.sha256(raw).hexdigest(), "needs":24, "snapshots":36, "development":8, "holdout":16, "zero_match":4, "embedding_model":"BAAI/bge-m3", "embedding_dimension":1024, "model_loads":1, "unique_strings_encoded":len(encoded), "total_vectors":len(encoded), "cold_model_load_ms":cold_load_ms, "embedding_latency_ms_total":enc_ms, "candidates":{c:{"development":metric(bench, rankings[c], bench["development_need_ids"]), "holdout":metric(bench, rankings[c], bench["holdout_need_ids"])} for c in rankings}, "oracle":metric(bench, {q:[{"id":x} for x in bench.get("strong_pairs",{}).get(q,[]) + bench.get("partial_pairs",{}).get(q,[])] for q in needs}, bench["holdout_need_ids"]), "reranker":"NOT RUN: optional model not provisioned", "v7":"NOT RUN: optional control not executed", "protocol_note":"Corrected V3 field-aware dense and V4 RRF instrumentation; original output preserved separately. Embeddings are batch-deduplicated and reused."}
    out = ROOT / "artifacts/experiments/ex025_r1_corrected_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    cache = ROOT / "artifacts/experiments/ex025_r1_bge_m3_embedding_cache.json"
    cache.write_text(json.dumps({"benchmark_sha256": result["benchmark_sha256"], "model_id":"BAAI/bge-m3", "revision":"5617a9f61b028005a4858fdac845db406aefb181", "normalization":"L2", "serialization":"canonical-v1", "vectors": encoded}, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
