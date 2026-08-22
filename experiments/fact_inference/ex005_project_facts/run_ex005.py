from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from app.modules.ai.providers.mistral import get_mistral_provider

from .contracts import ExtractedFact
from .deterministic import extract as deterministic_extract
from .evaluation import evaluate
from .structured import extract as structured_extract

ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks/project_fact_inference_v1.json"
ARTIFACT = ROOT / "artifacts/experiments/EX-005/ex005_results.json"


def load_benchmark() -> dict[str, Any]:
    payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    ids = [case["id"] for case in payload["cases"]]
    if len(ids) != 24 or len(set(ids)) != 24:
        raise ValueError("EX-005 requires 24 unique cases")
    if set(payload["development_ids"]) & set(payload["holdout_ids"]):
        raise ValueError("EX-005 development/holdout overlap")
    if set(ids) != set(payload["development_ids"]) | set(payload["holdout_ids"]):
        raise ValueError("EX-005 split does not cover benchmark")
    return payload


async def run_v1(cases: list[dict[str, Any]]) -> tuple[dict[str, list[ExtractedFact]], dict[str, dict[str, Any]]]:
    provider = get_mistral_provider()
    outputs: dict[str, list[ExtractedFact]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for case in cases:
        parsed, info = await structured_extract(provider, case["description"])
        outputs[case["id"]] = parsed.facts if parsed else []
        metadata[case["id"]] = info
    return outputs, metadata


async def run(scope: str = "all") -> dict[str, Any]:
    payload = load_benchmark()
    if scope not in {"all", "development", "holdout"}:
        raise ValueError("scope must be all, development, or holdout")
    cases = payload["cases"]
    dev = [case for case in cases if case["id"] in payload["development_ids"]]
    holdout = [case for case in cases if case["id"] in payload["holdout_ids"]]
    selected = dev if scope == "development" else holdout if scope == "holdout" else cases
    v0_outputs = {case["id"]: deterministic_extract(case["description"]) for case in cases}
    v0_meta = {case["id"]: {"valid": True, "latency_ms": 0, "usage": {}} for case in cases}
    v1_outputs, v1_meta = await run_v1(selected)
    output = {
        "experiment_id": "EX-005",
        "benchmark": "project_fact_inference_v1",
        "live_provider": "mistral",
        "scope": scope,
        "development": {"V0": evaluate(dev, v0_outputs, v0_meta), "V1": evaluate(dev, v1_outputs, v1_meta)} if scope in {"all", "development"} else None,
        "holdout": {"V0": evaluate(holdout, v0_outputs, v0_meta), "V1": evaluate(holdout, v1_outputs, v1_meta)} if scope in {"all", "holdout"} else None,
        "outputs": {
            "V0": {case["id"]: [fact.model_dump() for fact in v0_outputs[case["id"]]] for case in cases},
            "V1": {case["id"]: [fact.model_dump() for fact in v1_outputs[case["id"]]] for case in selected},
        },
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    if os.getenv("EX005_LIVE") != "1":
        raise SystemExit("Set EX005_LIVE=1 for the explicitly opt-in live Mistral experiment")
    print(json.dumps(asyncio.run(run(os.getenv("EX005_SCOPE", "all"))), indent=2, ensure_ascii=False))
