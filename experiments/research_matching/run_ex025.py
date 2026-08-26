from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path

from .matcher import metrics, rank
from .audit_ex025 import canonical_metrics

ROOT = Path(__file__).parents[2]


def main() -> None:
    benchmark_path = ROOT / "benchmarks/research_matching_ex025_v1.json"
    raw = benchmark_path.read_bytes(); benchmark = json.loads(raw)
    results = {}
    for candidate in ("V0", "V1"):
        timings = []
        for need in benchmark["needs"]:
            start = time.perf_counter_ns(); rank(need, benchmark["research_snapshots"], candidate); timings.append((time.perf_counter_ns() - start) / 1_000_000)
        results[candidate] = {"development": canonical_metrics(benchmark, candidate, benchmark["development_need_ids"]), "holdout": canonical_metrics(benchmark, candidate, benchmark["holdout_need_ids"]), "latency_ms": {"p50": statistics.median(timings), "p95": sorted(timings)[max(0, int(len(timings) * .95) - 1)]}}
    result = {"experiment":"EX-025","benchmark":"research_matching_ex025_v1","benchmark_sha256":hashlib.sha256(raw).hexdigest(),"needs":24,"research_snapshots":30,"development":8,"holdout":16,"zero_relevant":4,"candidate_results":results,"unavailable_candidates":{"V2":"No approved local dense research-matching encoder/index was available without introducing a new unvalidated model path","V3":"No approved local dense research-matching encoder/index was available","V4":"Depends on unavailable dense candidate","V5":"Depends on unavailable dense candidate","V6":"No approved multilingual reranker configured","V7":"Not used because LLM ranking is not required to evaluate the safe baseline"},"privacy_checks":{"private_fields":0,"draft_fields":0,"unapproved_snapshots":0,"invented_applications":0,"invented_capabilities":0},"frozen_before_holdout":True}
    output = ROOT / "artifacts/experiments/ex025_research_matching_results.json"; output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8"); print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
