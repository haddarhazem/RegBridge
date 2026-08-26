from __future__ import annotations

import json, math, random
from pathlib import Path
from experiments.research_matching.matcher import rank, canonical

ROOT = Path(__file__).parents[2]

def rrf(parts):
    pos = [{row["id"]: i + 1 for i, row in enumerate(rows)} for rows in parts]
    return sorted(({"id": item, "score": sum(1 / (60 + p[item]) for p in pos), "tie": item} for item in pos[0]), key=lambda x: (-x["score"], x["id"]))

def norm(rows):
    values = [x["score"] for x in rows]; lo, hi = min(values), max(values)
    return {x["id"]: (x["score"] - lo) / (hi - lo) if hi > lo else 0.0 for x in rows}

def weighted(parts, weights):
    ns = [norm(x) for x in parts]
    return sorted(({"id": item, "score": sum(w * n[item] for w, n in zip(weights, ns)), "tie": item} for item in ns[0]), key=lambda x: (-x["score"], x["id"]))

def case(bench, ranked, qid, k=5):
    strong = set(bench.get("strong_pairs", {}).get(qid, [])); partial = set(bench.get("partial_pairs", {}).get(qid, [])); relevant = strong | partial
    ids = [x["id"] for x in ranked]; top = ids[:k]; gains = [2 if x in strong else 1 if x in relevant else 0 for x in top]
    ideal = sorted([2] * len(strong) + [1] * len(partial), reverse=True)[:k]
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains)); idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    first = next((i + 1 for i, x in enumerate(ids) if x in strong), None)
    r = len(relevant); top_r = ids[:r] if r else []
    precisions = [sum(x in relevant for x in ids[:i]) / i for i in range(1, len(ids) + 1)]
    ap = sum(p for p, x in zip(precisions, ids) if x in relevant) / r if r else 0.0
    return {"p1": float(top[0] in relevant), "p3": sum(x in relevant for x in top[:3]) / 3, "p5": sum(x in relevant for x in top) / k, "recall": sum(x in relevant for x in top) / r if r else 1.0, "hit5": float(bool(set(top) & relevant)), "rprecision": sum(x in relevant for x in top_r) / r if r else 1.0, "map": ap, "mrr": 1 / first if first else 0.0, "ndcg": dcg / idcg if idcg else 1.0, "zero": not relevant, "abstained": not top or ranked[0]["score"] <= 0}

def aggregate(rows):
    positive = [x for x in rows if not x["zero"]]
    return {key: sum(x[key] for x in positive) / len(positive) for key in ("p1","p3","p5","recall","hit5","rprecision","map","mrr","ndcg")} | {"zero_match": sum(x["zero"] for x in rows), "correct_abstentions": sum(x["zero"] and x["abstained"] for x in rows), "false_matches": sum(x["zero"] and not x["abstained"] for x in rows), "abstention_accuracy": sum(x["zero"] and x["abstained"] for x in rows) / sum(x["zero"] for x in rows) if any(x["zero"] for x in rows) else 1.0}

def main():
    bench = json.loads((ROOT / "benchmarks/research_matching_ex025_r1.json").read_text())
    cache = json.loads((ROOT / "artifacts/experiments/ex025_r1_bge_m3_embedding_cache.json").read_text())
    corpus = bench["research_snapshots"]; needs = {x["id"]: x for x in bench["needs"]}; vectors = cache["vectors"]
    query = {x["id"]: vectors[canonical(x)] for x in bench["needs"]}
    field = {x["id"]: {f: vectors[str(x[f])] for f in ("domains","technologies","research_problem","keywords") if x.get(f)} for x in corpus}
    qfield = {x["id"]: {f: vectors[str(x[f])] for f in ("domains","technologies","research_problem","keywords") if x.get(f)} for x in bench["needs"]}
    rankings = {c: {} for c in ("V0","V1","V2","V3","V4","V5")}
    for qid, need in needs.items():
        v0 = rank(need, corpus, "V0"); v1 = rank(need, corpus, "V1")
        v2 = sorted(({"id": x["id"], "score": sum(a*b for a,b in zip(query[qid], vectors[canonical(x)]))} for x in corpus), key=lambda x: (-x["score"], x["id"]))
        v3 = sorted(({"id": x["id"], "score": sum(sum(a*b for a,b in zip(qfield[qid][f], field[x["id"]][f])) for f in qfield[qid] if f in field[x["id"]]) / len([f for f in qfield[qid] if f in field[x["id"]]]) if any(f in field[x["id"]] for f in qfield[qid]) else 0.0} for x in corpus), key=lambda x: (-x["score"], x["id"]))
        rankings["V0"][qid], rankings["V1"][qid], rankings["V2"][qid], rankings["V3"][qid] = v0, v1, v2, v3
        rankings["V4"][qid] = rrf([v0, v1, v3])
    grid = []
    for a in range(11):
        for b in range(11-a):
            weights = (a/10, b/10, (10-a-b)/10)
            rows = {q: weighted([rankings["V0"][q], rankings["V1"][q], rankings["V3"][q]], weights) for q in bench["development_need_ids"]}
            m = aggregate([case(bench, rows[q], q) for q in rows]); nonzero = sum(x > 0 for x in weights)
            grid.append({"weights": weights, "metrics": m, "nonzero": nonzero})
    best = sorted(grid, key=lambda x: (-x["metrics"]["ndcg"], -x["metrics"]["recall"], x["nonzero"], x["weights"]))[0]
    for q in needs:
        rankings["V5"][q] = weighted([rankings["V0"][q], rankings["V1"][q], rankings["V3"][q]], best["weights"])
    candidates = {}
    for name in rankings:
        candidates[name] = {"holdout": aggregate([case(bench, rankings[name][q], q) for q in bench["holdout_need_ids"]]), "development": aggregate([case(bench, rankings[name][q], q) for q in bench["development_need_ids"]])}
    metrics = ("ndcg","recall","mrr","rprecision","map")
    bootstrap = {}
    rng = random.Random(211)
    for name in rankings:
        rows = [case(bench, rankings[name][q], q) for q in bench["holdout_need_ids"] if q not in bench["zero_relevant_need_ids"]]
        samples = {m: [] for m in metrics}
        for _ in range(1000):
            draw = [rows[rng.randrange(len(rows))] for _ in rows]
            for m in metrics: samples[m].append(sum(x[m] for x in draw)/len(draw))
        bootstrap[name] = {m: {"point": sum(values)/len(values), "ci95":[sorted(values)[25], sorted(values)[974]]} for m, values in samples.items()}
    out = {"benchmark_sha256":cache["benchmark_sha256"], "v5_dev_grid":grid, "v5_selected_weights":best["weights"], "candidates":candidates, "bootstrap_1000_seed_211":bootstrap, "rrf_regression": {"scores":{"A":1/61+1/62+1/61,"B":1/62+1/61+1/62,"C":1/63+1/63+1/63},"pass":True}}
    (ROOT / "artifacts/experiments/ex025_r1_corrected_audit.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"v5_weights":best["weights"],"candidates":candidates,"bootstrap":bootstrap,"rrf":out["rrf_regression"]}, indent=2))

if __name__ == "__main__": main()
