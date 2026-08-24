"""Run the frozen EX-023-S1 supplementary semantic fallback holdout."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.modules.ai.providers.mistral import get_mistral_provider
from experiments.opportunity_brief_verification.run_ex023 import evaluate_semantic, evaluate_v0, provider_smoke

ROOT = Path(__file__).parents[2]


async def run() -> dict:
    benchmark = json.loads((ROOT / "benchmarks/investor_opportunity_brief_ex023_s1.json").read_text(encoding="utf-8"))
    v0 = evaluate_v0(benchmark["cases"])
    smoke = await provider_smoke()
    result = {"experiment": "EX-023-S1", "benchmark": benchmark["benchmark"], "frozen": benchmark["frozen"], "v0": v0, "provider_smoke": smoke}
    if smoke["status"] == "PASS":
        provider = get_mistral_provider()
        result["v1"] = await evaluate_semantic(provider, benchmark["cases"], hybrid=False)
        result["v2"] = await evaluate_semantic(provider, benchmark["cases"], hybrid=True)
    else:
        result["v1"] = {"status": "BLOCKED"}
        result["v2"] = {"status": "BLOCKED"}
    output = ROOT / "artifacts/experiments/ex023_s1_investor_opportunity_brief_verification_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), indent=2, ensure_ascii=False))
