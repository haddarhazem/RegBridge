from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.modules.ai.providers.mistral import get_mistral_provider

from .artifact_store import write_completed_run
from .runner_r2 import ARTIFACT_ROOT, _aggregate, _v4
from .runner_r1 import evaluate_candidate

ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks/research_extraction_ex024_r3_holdout_v1.json"
R3_ARTIFACT_ROOT = ROOT / "artifacts/experiments/ex024/r3"
FIELDS8 = ("domains", "technologies", "research_problem", "methodology", "main_results", "explicit_applications", "keywords", "limitations")


async def run(provider=None, *, run_id: str | None = None):
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    if not benchmark.get("frozen") or len(benchmark["cases"]) != 16 or sum(len(case["gold"]) for case in benchmark["cases"]) != 128:
        raise RuntimeError("EX-024-R3 benchmark count gate failed")
    for field in FIELDS8:
        supported = sum(bool(case["gold"].get(field)) for case in benchmark["cases"])
        if supported != 8:
            raise RuntimeError(f"EX-024-R3 balance gate failed for {field}")
    provider = provider or get_mistral_provider()
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = {candidate: [await evaluate_candidate(provider, case, candidate) for case in benchmark["cases"]] for candidate in ("V0", "V1", "V2", "V3")}
    rows["V4"] = [await _v4(provider, case) for case in benchmark["cases"]]
    result = {"experiment":"EX-024-R3","research_question":"RQ-024","run_id":run_id,"benchmark_id":benchmark["benchmark_id"],"benchmark_sha256":"7844F7AD2A2FC5A9883FAD873C7252B60B1E61B18E1EE09760F4E70F60220A17","model":getattr(provider,"model",None),"candidates":["V0","V1","V2","V3","V4"],"gates":{"critical_unsupported":0,"recall":0.70,"usable":0.90,"application_precision":0.90,"application_recall":0.80,"provenance":0.95,"v4_exact_copy":1.0,"v4_abstract_provenance":1.0},"aggregates":{candidate:_aggregate(candidate,rows[candidate],benchmark["cases"]) for candidate in rows},"rows":rows}
    write_completed_run(R3_ARTIFACT_ROOT / run_id / "results.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
