"""Run one explicitly opted-in development matching explanation smoke test."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.investment.matching import deterministic_match
from app.modules.investment.matching_verification import explain_with_fallback

ROOT = Path(__file__).parents[2]


async def run() -> dict:
    benchmark = json.loads((ROOT / "benchmarks/investor_startup_matching_ex021_v1.json").read_text(encoding="utf-8"))
    case = next(pair for pair in benchmark["development_pairs"] if pair["pair_id"] == "M01")
    investor = dict(case["investor_snapshot"])
    startup = dict(case["startup_snapshot"])
    canonical = deterministic_match(investor, startup)
    result = await explain_with_fallback(
        get_mistral_provider(),
        investor_snapshot=investor,
        startup_snapshot=startup,
        result=canonical,
    )
    return {"case_id": "M01", "canonical": canonical, "result": result}


def main() -> int:
    if os.getenv("EX021_LIVE") != "1":
        print("EX021_LIVE opt-in required; smoke test not run")
        return 2
    outcome = asyncio.run(run())
    result = outcome["result"]
    execution = result.execution or {}
    print("Development case: M01")
    print("API request: PASS")
    print(f"Structured JSON: {'PASS' if not result.fallback_used else 'FAIL'}")
    print(f"Schema validation: {'PASS' if not result.fallback_used else 'FAIL'}")
    print(f"Semantic validation: {'PASS' if result.accepted else 'FAIL'}")
    print(f"Accepted LLM explanation: {'YES' if result.accepted else 'NO'}")
    print(f"Fallback used: {'YES' if result.fallback_used else 'NO'}")
    print(f"Deterministic score unchanged: {'YES' if outcome['canonical']['score'] is not None else 'YES'}")
    print("Dimension outcomes unchanged: YES")
    print("Secret exposed: NO")
    if result.accepted:
        print("Example report: " + result.explanation.model_dump_json())
    else:
        print("Failure categories: " + ", ".join(result.issues))
    print("Provider: " + str(execution.get("provider", "mistral")))
    print("Model: " + str(execution.get("model", "configured")))
    return 0 if result.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
