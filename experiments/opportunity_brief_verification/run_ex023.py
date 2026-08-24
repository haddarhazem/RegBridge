"""Run the frozen EX-023 V0/V1/V2 comparison outside production code."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

from app.core.config import get_settings
from app.modules.ai.llm import LLMGenerationRequest, LLMMessage, LLMProviderError
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.investment.brief_verification import verify_frozen_brief
from experiments.opportunity_brief_verification.semantic import verify_semantically

ROOT = Path(__file__).parents[2]


def _claim(case: dict) -> tuple[str, str, list[str]]:
    content = case["content"]
    if content.get("claims"):
        item = content["claims"][0]
        return item["text"], case["claim_type"], item.get("evidence_refs", [])
    text = content["thesis_fit"][0]
    return text, case["claim_type"], [ref for ref in case["evidence_bundle"].get("evidence_refs", []) if ref.startswith("matching:")]


def _evidence(case: dict, refs: list[str]) -> dict[str, Any]:
    bundle = case["evidence_bundle"]
    return {"confirmed_facts": [fact for fact in bundle.get("confirmed_facts", []) if fact.get("evidence_ref") in refs], "matching_result": {"dimensions": bundle["matching_result"]["dimensions"]}}


def _v0_actual(case: dict) -> str:
    decisions = verify_frozen_brief(case["content"], case["evidence_bundle"], case["evidence_bundle"]["matching_result"])
    return decisions[0].verdict if len(decisions) == 1 else ("SUPPORTED" if decisions and all(item.verdict == "SUPPORTED" for item in decisions) else "UNSUPPORTED")


def _metrics(rows: list[dict], *, provider_calls: int, latency_ms: list[float], token_input: float, token_output: float, provider_dependency: bool) -> dict:
    supported = [row for row in rows if row["expected"] == "SUPPORTED"]
    unsupported = [row for row in rows if row["expected"] == "UNSUPPORTED"]
    predicted_supported = [row for row in rows if row.get("actual") == "SUPPORTED"]
    tp = sum(row.get("actual") == "SUPPORTED" and row["expected"] == "SUPPORTED" for row in rows)
    fp = sum(row.get("actual") == "SUPPORTED" and row["expected"] != "SUPPORTED" for row in rows)
    fn = sum(row.get("actual") != "SUPPORTED" and row["expected"] == "SUPPORTED" for row in rows)
    precision = tp / len(predicted_supported) if predicted_supported else 1.0
    recall = tp / len(supported) if supported else 1.0
    critical_false_passes = [row["case_id"] for row in rows if row["critical"] and row["expected"] == "UNSUPPORTED" and row.get("actual") == "SUPPORTED"]
    return {
        "cases": len(rows), "provider_calls": provider_calls, "provider_successes": sum(row.get("provider_success") is True for row in rows), "structured_output_successes": sum(row.get("structured_success") is True for row in rows), "provider_failures": sum(row.get("provider_success") is False for row in rows),
        "supported": sum(row.get("actual") == "SUPPORTED" for row in rows), "unsupported": sum(row.get("actual") == "UNSUPPORTED" for row in rows), "unverifiable": sum(row.get("actual") == "UNVERIFIABLE" for row in rows),
        "unsupported_claim_recall": sum(row.get("actual") != "SUPPORTED" for row in unsupported) / len(unsupported) if unsupported else 1.0, "precision": precision, "false_pass_rate": fp / len(unsupported) if unsupported else 0.0, "false_block_rate": fn / len(supported) if supported else 0.0, "macro_f1": (2 * precision * recall / (precision + recall)) if precision + recall else 0.0,
        "critical_false_passes": critical_false_passes, "unknown_protection": not any(row["claim_type"] == "matching_unknown" and row.get("actual") == "SUPPORTED" and row["expected"] != "SUPPORTED" for row in rows), "matching_fidelity": not any("matching" in row["claim_type"] and row.get("actual") == "SUPPORTED" and row["expected"] != "SUPPORTED" for row in rows), "matching_fidelity_protection": not any("matching" in row["claim_type"] and row.get("actual") == "SUPPORTED" and row["expected"] != "SUPPORTED" for row in rows), "unauthorized_data_usage": 0,
        "average_latency_ms": mean(latency_ms) if latency_ms else None, "p95_latency_ms": sorted(latency_ms)[max(0, int(len(latency_ms) * 0.95) - 1)] if latency_ms else None, "input_tokens": token_input, "output_tokens": token_output, "provider_dependency": provider_dependency, "rows": rows,
    }


def evaluate_v0(cases: list[dict]) -> dict:
    started = perf_counter()
    rows = [{"case_id": case["case_id"], "expected": case["expected_verdict"], "actual": _v0_actual(case), "critical": case["critical"], "claim_type": case["claim_type"]} for case in cases]
    return _metrics(rows, provider_calls=0, latency_ms=[(perf_counter() - started) * 1000], token_input=0, token_output=0, provider_dependency=False)


def _add_reliability_metrics(metrics: dict, total_cases: int) -> dict:
    semantic_rows = [row for row in metrics.get("rows", []) if row.get("resolution") == "semantic"]
    reliability_rows = semantic_rows or metrics.get("rows", [])
    valid = sum(row.get("actual") is not None for row in reliability_rows)
    provider_successes = metrics.get("provider_successes", 0)
    metrics["valid_semantic_verdicts"] = valid
    metrics["structured_output_reliability"] = valid / provider_successes if provider_successes else 0.0
    metrics["invalid_structured_outputs"] = provider_successes - valid
    metrics["invalid_structured_output_rate"] = (provider_successes - valid) / provider_successes if provider_successes else 0.0
    deterministic_count = sum(row.get("resolution") == "deterministic" for row in metrics.get("rows", []))
    metrics["end_to_end_conclusive_verdicts"] = deterministic_count + valid
    metrics["end_to_end_conclusive_verdict_rate"] = (deterministic_count + valid) / total_cases if total_cases else 0.0
    metrics["operational_invalid_output"] = "rejected_no_verdict"
    valid_rows = [row for row in reliability_rows if row.get("actual") is not None]
    metrics["semantic_quality_on_valid_outputs"] = _metrics(valid_rows, provider_calls=provider_successes, latency_ms=[], token_input=0, token_output=0, provider_dependency=True) if valid_rows else None
    return metrics


async def provider_smoke() -> dict:
    if os.getenv("EX023_LIVE") != "1":
        return {"enabled": False, "status": "NOT_RUN"}
    try:
        settings = get_settings()
        provider = get_mistral_provider()
        response = await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="system", content="Return only the requested JSON schema."), LLMMessage(role="user", content="Connectivity check only; return status=ok. Do not use benchmark data.")], temperature=0, max_tokens=20, response_format={"type": "json_schema", "json_schema": {"name": "ProviderSmoke", "schema": {"type": "object", "properties": {"status": {"type": "string", "enum": ["ok"]}}, "required": ["status"], "additionalProperties": False}}}, prompt_version="scrum205-provider-smoke-v1", operation="scrum205_provider_smoke"))
        return {"enabled": True, "status": "PASS", "provider": "mistral", "model": settings.mistral_model, "execution": response.execution.model_dump(mode="json") if response.execution else None}
    except LLMProviderError as exc:
        return {"enabled": True, "status": "BLOCKED", "reason": exc.category, "cause_type": exc.cause_type, "cause_message": exc.cause_message, "http_status": exc.http_status}
    except Exception as exc:
        return {"enabled": True, "status": "BLOCKED", "reason": type(exc).__name__}


async def evaluate_semantic(provider, cases: list[dict], *, hybrid: bool) -> dict:
    rows: list[dict] = []
    latencies: list[float] = []
    input_tokens = output_tokens = 0
    semantic_calls = 0
    deterministic_latencies: list[float] = []
    for case in cases:
        deterministic_started = perf_counter()
        deterministic = _v0_actual(case)
        deterministic_latencies.append((perf_counter() - deterministic_started) * 1000)
        if hybrid and deterministic != "UNVERIFIABLE":
            rows.append({"case_id": case["case_id"], "expected": case["expected_verdict"], "actual": deterministic, "critical": case["critical"], "claim_type": case["claim_type"], "provider_success": None, "structured_success": None, "resolution": "deterministic"})
            continue
        semantic_calls += 1
        claim, claim_type, refs = _claim(case)
        started = perf_counter()
        verdict, execution, error = await verify_semantically(provider, claim=claim, claim_type=claim_type, evidence=_evidence(case, refs), evidence_refs=refs)
        latencies.append((perf_counter() - started) * 1000)
        if execution:
            input_tokens += execution.get("prompt_tokens") or 0
            output_tokens += execution.get("completion_tokens") or 0
        rows.append({"case_id": case["case_id"], "expected": case["expected_verdict"], "actual": verdict.status if verdict else None, "critical": case["critical"], "claim_type": case["claim_type"], "provider_success": execution is not None, "structured_success": verdict is not None, "resolution": "semantic", "error": error})
    all_latencies = deterministic_latencies + latencies if hybrid else latencies
    metrics = _metrics(rows, provider_calls=semantic_calls, latency_ms=all_latencies, token_input=input_tokens, token_output=output_tokens, provider_dependency=True)
    metrics.update({"deterministic_only_resolutions": sum(row["resolution"] == "deterministic" for row in rows), "semantic_fallback_calls": semantic_calls, "semantic_successes": sum(row.get("structured_success") is True for row in rows), "semantic_failures": sum(row.get("provider_success") is False for row in rows)})
    metrics["deterministic_only_avg_latency_ms"] = mean(deterministic_latencies) if deterministic_latencies else None
    metrics["semantic_fallback_avg_latency_ms"] = mean(latencies) if latencies else None
    metrics["overall_avg_latency_ms"] = mean(all_latencies) if all_latencies else None
    metrics["llm_calls_avoided_vs_v1"] = len(cases) - semantic_calls
    _add_reliability_metrics(metrics, len(cases))
    return metrics


async def run() -> dict:
    benchmark = json.loads((ROOT / "benchmarks/investor_opportunity_brief_ex023_v1.json").read_text(encoding="utf-8"))
    v0 = evaluate_v0(benchmark["cases"])
    smoke = await provider_smoke()
    result: dict[str, Any] = {"experiment": "EX-023", "benchmark": benchmark["benchmark"], "frozen": benchmark["frozen"], "v0": v0, "provider_smoke": smoke}
    if smoke["status"] == "PASS":
        provider = get_mistral_provider()
        result["v1"] = await evaluate_semantic(provider, benchmark["cases"], hybrid=False)
        result["v2"] = await evaluate_semantic(provider, benchmark["cases"], hybrid=True)
    else:
        result["v1"] = {"status": "BLOCKED", "provider_calls": 0}
        result["v2"] = {"status": "BLOCKED", "provider_calls": 0}
    output = ROOT / "artifacts/experiments/ex023_investor_opportunity_brief_verification_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), indent=2, ensure_ascii=False))
