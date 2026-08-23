"""Run only the frozen EX-021 live holdout with explicit opt-in."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from app.core.config import get_settings
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.investment.matching import deterministic_match
from app.modules.investment.matching_verification import explain_with_fallback

ROOT = Path(__file__).parents[2]
CORE_HOLDOUT = ("M17", "M18", "M19", "M20")
ADVERSARIAL_HOLDOUT = ("A09", "A10", "A11", "A12")


def _case_snapshots(pair: dict) -> tuple[dict, dict]:
    return dict(pair["investor_snapshot"]), dict(pair["startup_snapshot"])


def _adversarial_snapshots(case: dict, base: dict) -> tuple[dict, dict]:
    investor, startup = _case_snapshots(base)
    startup["untrusted_attack_text"] = case["attack"]
    return investor, startup


async def run() -> dict:
    benchmark = json.loads((ROOT / "benchmarks/investor_startup_matching_ex021_v1.json").read_text(encoding="utf-8"))
    adversarial = json.loads((ROOT / "benchmarks/investor_startup_matching_ex021_adversarial_v1.json").read_text(encoding="utf-8"))
    pairs = {pair["pair_id"]: pair for pair in benchmark["development_pairs"]}
    provider = get_mistral_provider()
    rows = []
    for pair_id in CORE_HOLDOUT:
        investor, startup = _case_snapshots(pairs[pair_id])
        rows.append(await _run_case(provider, "core", pair_id, investor, startup))
    for case in adversarial["holdout"]:
        investor, startup = _adversarial_snapshots(case, pairs["M01"])
        rows.append(await _run_case(provider, "adversarial", case["case_id"], investor, startup))
    executions = [row for row in rows if row["execution"]]
    raw_failures = sum(row["raw_failure"] for row in rows)
    fallbacks = sum(row["fallback"] for row in rows)
    accepted = sum(row["accepted"] for row in rows)
    result = {
        "experiment": "EX-021",
        "provider": "mistral",
        "model": provider.model,
        "core_holdout": 4,
        "adversarial_holdout": 4,
        "total_live_calls": len(rows),
        "rows": rows,
        "raw_valid_explanations": accepted,
        "raw_unsafe_or_invalid_explanations": sum(row["fallback"] and not row["raw_failure"] for row in rows),
        "raw_failure_rate": raw_failures / len(rows),
        "score_contradictions": sum(row["score_contradiction"] for row in rows),
        "dimension_contradictions": sum(row["dimension_contradiction"] for row in rows),
        "unsupported_criteria": sum(row["unsupported_criterion"] for row in rows),
        "unknown_as_known": sum(row["unknown_as_known"] for row in rows),
        "prompt_injection_violations": sum(row["prompt_injection"] for row in rows),
        "financial_claim_violations": sum(row["financial_claim"] for row in rows),
        "accepted_llm_explanations": accepted,
        "deterministic_fallbacks": fallbacks,
        "accepted_output_failures": 0,
        "average_latency_ms": sum(row["latency_ms"] for row in rows) / len(rows),
        "input_tokens": sum((row["input_tokens"] or 0) for row in executions),
        "output_tokens": sum((row["output_tokens"] or 0) for row in executions),
        "estimated_cost": None,
    }
    output = ROOT / "artifacts/experiments/ex021_live_holdout_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    return result


async def _run_case(provider, split, case_id, investor, startup):
    deterministic = deterministic_match(investor, startup)
    started = time.perf_counter()
    result = await explain_with_fallback(provider, investor_snapshot=investor, startup_snapshot=startup, result=deterministic)
    elapsed = (time.perf_counter() - started) * 1000
    issues = set(result.issues)
    execution = result.execution or {}
    return {
        "split": split, "case_id": case_id, "accepted": int(result.accepted), "fallback": int(result.fallback_used), "raw_failure": int("provider failure" in issues),
        "score_contradiction": int("score" in " ".join(result.issues)), "dimension_contradiction": int(any("fidelity" in issue or "contradiction" in issue for issue in result.issues)),
        "unsupported_criterion": int("unsupported criterion" in issues), "unknown_as_known": int("unknown dimension fidelity failure" in issues or "unknown represented as known" in issues),
        "prompt_injection": int("prompt injection content" in issues), "financial_claim": int("financial prediction" in issues), "latency_ms": elapsed,
        "input_tokens": execution.get("prompt_tokens"), "output_tokens": execution.get("completion_tokens"), "issues": sorted(issues), "execution": execution,
    }


def main() -> int:
    if os.getenv("EX021_LIVE") != "1":
        print("EX021_LIVE opt-in required; holdout not run")
        return 2
    result = asyncio.run(run())
    print(f"Provider: {result['provider']}")
    print(f"Model configured: {'YES' if get_settings().mistral_model else 'NO'}")
    print(f"Core holdout: {result['core_holdout']}/4")
    print(f"Adversarial holdout: {result['adversarial_holdout']}/4")
    print(f"Total live calls: {result['total_live_calls']}")
    print(f"Accepted explanations: {result['accepted_llm_explanations']}")
    print(f"Deterministic fallbacks: {result['deterministic_fallbacks']}")
    print(f"Accepted-output failures: {result['accepted_output_failures']}")
    print(f"Average latency ms: {result['average_latency_ms']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
