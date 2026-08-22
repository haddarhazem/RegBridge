"""Run the frozen EX-003 V0/V1/V2 comparison.

This module is research-only. It reads the fixed benchmark and never writes
to Qdrant or production state.
"""

from __future__ import annotations

import asyncio
import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.ai.llm import LLMGenerationError, LLMProviderError
from app.modules.ai.providers.mistral import get_mistral_provider

from .contracts import ClaimAssessment, VerificationInput, VerificationOutput
from .deterministic import verify_structure
from .input_projection import forbidden_fields, project_verifier_input
from .prompt import build_request


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks/response_verification_v1.jsonl"
ARTIFACTS = ROOT / "artifacts/experiments/EX-003"
PROMPT_VERSION = "EX-003-V2-prompt-v1"


def load_cases() -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in BENCHMARK.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = [row for row in rows if row["annotation_status"] == "human_validated"]
    assert len(selected) == 24
    assert all(row["id"] != "VER-030" for row in selected)
    return selected


def dump_output(output: VerificationOutput | None) -> dict[str, Any] | None:
    return output.model_dump(mode="json") if output is not None else None


def v0(item: VerificationInput) -> VerificationOutput:
    return VerificationOutput(verdict="pass", reasons=["V0 accepts every answer without verification"])


def v1(item: VerificationInput) -> VerificationOutput:
    return verify_structure(item)


async def v2(item: VerificationInput) -> tuple[VerificationOutput | None, dict[str, int | float], str | None]:
    provider = get_mistral_provider()
    response = await provider.generate(build_request(item))
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            return None, response.usage, "structured JSON was not returned"
        try:
            parsed = json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None, response.usage, "structured JSON was not parseable"
    try:
        return VerificationOutput.model_validate(parsed), response.usage, None
    except Exception:
        return None, response.usage, "structured output failed the bounded schema"


def human_claims(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {claim["claim_id"]: claim for claim in row["claims"]}


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower, upper = int(index), min(int(index) + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def metrics(rows: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["id"]: row for row in rows}
    successful = [item for item in predictions if item["output"] is not None]
    prediction_by_id = {item["case_id"]: item for item in successful}
    allowed = {"pass", "pass_with_warnings"}
    block_rows = [row for row in rows if row["expected_verdict"] == "block"]
    non_block_rows = [row for row in rows if row["expected_verdict"] != "block"]
    false_pass = sum(prediction_by_id.get(row["id"], {}).get("output", {}).get("verdict") in allowed for row in block_rows)
    false_block = sum(prediction_by_id.get(row["id"], {}).get("output", {}).get("verdict") == "block" for row in non_block_rows)
    confusion: dict[str, dict[str, int]] = {}
    for row in rows:
        predicted = prediction_by_id.get(row["id"], {}).get("output", {}).get("verdict")
        if predicted is None:
            continue
        confusion.setdefault(row["expected_verdict"], {})[predicted] = confusion.setdefault(row["expected_verdict"], {}).get(predicted, 0) + 1

    allowed_claims = [
        claim
        for row in rows
        if prediction_by_id.get(row["id"], {}).get("output", {}).get("verdict") in allowed
        for claim in row["claims"]
        if claim["material"]
    ]
    unsafe = sum(claim["expected_support"] in {"unsupported", "contradicted"} for claim in allowed_claims)
    coverage_denominator = sum(bool(claim["expected_evidence_ids"]) for row in rows for claim in row["claims"] if claim["material"])
    coverage_numerator = 0
    for row in rows:
        output_claims = {claim["claim_id"]: claim for claim in prediction_by_id.get(row["id"], {}).get("output", {}).get("claims", [])}
        for claim in row["claims"]:
            if claim["material"] and claim["expected_evidence_ids"] and set(output_claims.get(claim["claim_id"], {}).get("evidence_ids", [])) & set(claim["expected_evidence_ids"]):
                coverage_numerator += 1
    latencies = [float(item["latency_ms"]) for item in predictions]
    return {
        "sample_count": len(predictions),
        "successful_predictions": len(successful),
        "failed_predictions": len(predictions) - len(successful),
        "unsupported_claim_rate": unsafe / len(allowed_claims) if allowed_claims else None,
        "public_source_attribution_correctness": sum(row["expected_public_source_correct"] for row in rows) / len(rows),
        "citation_evidence_coverage": coverage_numerator / coverage_denominator if coverage_denominator else None,
        "false_pass_rate": false_pass / len(block_rows) if block_rows else None,
        "false_block_rate": false_block / len(non_block_rows) if non_block_rows else None,
        "confusion_matrix": confusion,
        "latency_ms": {"median": statistics.median(latencies) if latencies else None, "p95": percentile(latencies, 0.95)},
        "usage": {
            "prompt_tokens": sum(float(item.get("usage", {}).get("prompt_tokens", 0)) for item in predictions),
            "completion_tokens": sum(float(item.get("usage", {}).get("completion_tokens", 0)) for item in predictions),
            "total_tokens": sum(float(item.get("usage", {}).get("total_tokens", 0)) for item in predictions),
        },
    }


async def run_variant(name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for row in rows:
        item = project_verifier_input(row)
        assert not (set(item.model_dump()) & forbidden_fields())
        started = time.perf_counter()
        usage: dict[str, int | float] = {}
        error: str | None = None
        output: VerificationOutput | None = None
        try:
            if name == "V0":
                output = v0(item)
            elif name == "V1":
                output = v1(item)
            else:
                output, usage, error = await v2(item)
        except (LLMProviderError, LLMGenerationError) as exc:
            error = type(exc).__name__
        elapsed = (time.perf_counter() - started) * 1000
        results.append({"case_id": row["id"], "output": dump_output(output), "error": error, "latency_ms": elapsed, "usage": usage})
    return results


async def main(output_stem: str = "ex003_run", metrics_stem: str = "ex003_metrics") -> None:
    rows = load_cases()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    all_results: dict[str, Any] = {
        "experiment_id": "EX-003",
        "run_id": datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ"),
        "dataset": "response_verification_v1",
        "case_ids": [row["id"] for row in rows],
        "prompt_version": PROMPT_VERSION,
        "variants": {},
    }
    for name in ("V0", "V1", "V2"):
        predictions = await run_variant(name, rows)
        all_results["variants"][name] = {"predictions": predictions, "metrics": metrics(rows, predictions)}
        print(f"{name}: {len(predictions)} cases, failures={sum(item['error'] is not None for item in predictions)}")
    (ARTIFACTS / f"{output_stem}.json").write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    (ARTIFACTS / f"{metrics_stem}.json").write_text(json.dumps({name: value["metrics"] for name, value in all_results["variants"].items()}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-stem", default="ex003_run")
    parser.add_argument("--metrics-stem", default="ex003_metrics")
    args = parser.parse_args()
    asyncio.run(main(output_stem=args.output_stem, metrics_stem=args.metrics_stem))
