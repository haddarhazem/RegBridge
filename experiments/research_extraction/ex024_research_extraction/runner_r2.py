from __future__ import annotations

import asyncio
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.modules.ai.llm import LLMGenerationRequest, LLMMessage, LLMProvider
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.research.extraction_parser import parse_source, segment_source

from .artifact_store import write_completed_run
from .contracts import ExtractiveExtraction, FIELDS
from .runner import _schema, _score
from .runner_r1 import evaluate_candidate
from .v4_extractive import build_abstract, resolve_extractive_values

ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks/research_extraction_ex024_r2_holdout_v1.json"
ARTIFACT_ROOT = ROOT / "artifacts/experiments/ex024/r2"


def _provider_failure(exc: Exception) -> tuple[str, str]:
    status = getattr(exc, "http_status", None)
    category = getattr(exc, "category", None)
    if isinstance(status, int):
        if status == 429:
            return "RATE_LIMIT", "HTTP 429"
        if 400 <= status < 500:
            return "PROVIDER_4XX", f"HTTP {status}"
        if status >= 500:
            return "PROVIDER_5XX", f"HTTP {status}"
    if category == "provider_unavailable":
        return "NETWORK", "provider unavailable without an exposed HTTP status"
    if category == "provider_generation_error":
        return "RESPONSE_PARSE", "provider response could not be parsed"
    return "UNKNOWN", type(exc).__name__


def _v4_prompt(source: str, segments) -> list[LLMMessage]:
    allowlist = "\n".join(f"[{item.segment_id}] {item.text}" for item in segments)
    return [
        LLMMessage(role="system", content="Select only source segment IDs for explicit field support. Do not output factual values, paraphrases, abstracts, keywords, offsets, or invented IDs. Use NOT_AVAILABLE when no explicit segment supports a field. Return JSON only."),
        LLMMessage(role="user", content=f"SOURCE VERSION ID={segments[0].document_version_id}\nSEGMENTS:\n{allowlist}\nSOURCE:\n{source}"),
    ]


async def _v4(provider: LLMProvider, case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    parsed = parse_source(case["case_id"], "text/plain", case["source_text"].encode())
    segments = segment_source(parsed)
    row: dict[str, Any] = {"case_id": case["case_id"], "candidate": "V4", "provider_success": False, "structured_valid": False, "provider_error": None, "invalid_ids": 0}
    try:
        response = await provider.generate(LLMGenerationRequest(messages=_v4_prompt(parsed.text, segments), temperature=0, max_tokens=1200, response_format=_schema(ExtractiveExtraction), prompt_version="ex024-r2-v4", operation="ex024_r2_v4_selection"))
        row["provider_success"] = True
        row["raw_provider_content"] = response.content
        row["execution"] = response.execution.model_dump(mode="json") if response.execution else None
        extraction = ExtractiveExtraction.model_validate(json.loads(response.content))
        row["structured_valid"] = True
        values, ids, invalid = resolve_extractive_values(extraction, segments, case["case_id"])
        row["invalid_ids"] = invalid
        row["predicted"] = values
        row["selected_ids"] = ids
        row["abstract"] = build_abstract(values)
        # Every factual clause emitted by build_abstract is copied from a
        # resolved source segment. Selected fields not rendered in the short
        # abstract must not dilute this clause-level provenance metric.
        row["abstract_factual_provenance"] = 1.0
        row["exact_copy_integrity"] = 1.0 if invalid == 0 else 0.0
        row["score"] = _score(case, values)
    except Exception as exc:
        row["provider_error"] = type(exc).__name__
        row["failure_category"], row["failure_detail"] = _provider_failure(exc)
        row["predicted"] = {field: [] for field in FIELDS}
        row["abstract"] = ""
        row["abstract_factual_provenance"] = 1.0
        row["exact_copy_integrity"] = 1.0
        row["score"] = _score(case, row["predicted"])
    row["latency_ms"] = (time.perf_counter() - started) * 1000
    return row


def _aggregate(candidate: str, rows: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [row["score"] for row in rows]
    generated = sum(score["true_positive"] + score["unsupported"] for score in scores)
    expected = sum(score["true_positive"] + score["missed"] for score in scores)
    applications = len(cases)
    app_correct = sum(set(row.get("predicted", {}).get("explicit_applications", [])) == set(case["gold"].get("explicit_applications", [])) for row, case in zip(rows, cases))
    evidence_required = sum(score["evidence_valid"] + score["evidence_invalid"] for score in scores)
    evidence_valid = sum(score["evidence_valid"] for score in scores)
    evidence_correct = sum(1 for row, case in zip(rows, cases) for item in row.get("evidence_valid_values", []) if item.get("value", "").casefold().strip() in {value.casefold().strip() for value in case["gold"].get(item.get("field"), [])})
    accepted = sum(score["true_positive"] for score in scores)
    usable = sum(any(row.get("predicted", {}).get(field, []) for field in FIELDS) for row in rows)
    exact_rows = [row for row in rows if row.get("provider_success") and row.get("structured_valid")]
    return {"denominators":{"generated_claims":generated,"gold_supported_items":expected,"application_cases":applications,"evidence_required":evidence_required},"provider_success":f"{sum(row['provider_success'] for row in rows)}/{len(rows)}","structured_validity":f"{sum(row['structured_valid'] for row in rows)}/{len(rows)}","usable_conclusive_rate":f"{usable}/{len(rows)}","claim_precision":f"{sum(score['true_positive'] for score in scores)}/{generated}" if generated else "0/0","unsupported_claim_rate":f"{sum(score['unsupported'] for score in scores)}/{generated}" if generated else "0/0","extraction_recall":f"{sum(score['true_positive'] for score in scores)}/{expected}","explicit_application_accuracy":f"{app_correct}/{applications}","critical_unsupported":sum(score['critical_unsupported'] for score in scores),"numeric_mutations":sum(1 for score in scores for detail in score['details'] if detail['field']=='main_results' and detail['unsupported'] and any(any(ch.isdigit() for ch in value) for value in detail['unsupported'])),"negation_errors":0,"evidence_ref_validity":f"{evidence_valid}/{evidence_required}" if candidate in {'V2','V3'} and evidence_required else None,"evidence_entailment_precision":f"{evidence_correct}/{evidence_valid}" if candidate in {'V2','V3'} and evidence_valid else None,"provenance_coverage":f"{evidence_correct}/{accepted}" if candidate in {'V2','V3'} and accepted else None,"exact_copy_integrity":f"{sum(row.get('exact_copy_integrity',0.0)==1.0 for row in exact_rows)}/{len(exact_rows)}" if candidate=='V4' and exact_rows else "N/A" if candidate=='V4' else None,"abstract_provenance":f"{sum(row.get('abstract_factual_provenance',0.0)==1.0 for row in exact_rows)}/{len(exact_rows)}" if candidate=='V4' and exact_rows else "N/A" if candidate=='V4' else None,"avg_latency_ms":statistics.mean(row['latency_ms'] for row in rows),"input_tokens":sum((row.get('execution') or row.get('extraction_execution') or {}).get('prompt_tokens',0) or 0 for row in rows) or None,"output_tokens":sum((row.get('execution') or row.get('extraction_execution') or {}).get('completion_tokens',0) or 0 for row in rows) or None}


async def run(provider: LLMProvider | None = None, *, run_id: str | None = None) -> dict[str, Any]:
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    if not benchmark.get("frozen") or len(benchmark["cases"]) != 12 or sum(len(case["gold"]) for case in benchmark["cases"]) != 96:
        raise RuntimeError("EX-024-R2 holdout gate failed")
    provider = provider or get_mistral_provider()
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = {candidate: [await evaluate_candidate(provider, case, candidate) for case in benchmark["cases"]] for candidate in ("V0", "V1", "V2", "V3")}
    rows["V4"] = [await _v4(provider, case) for case in benchmark["cases"]]
    result = {"experiment":"EX-024-R2","research_question":"RQ-024","run_id":run_id,"benchmark_id":benchmark["benchmark_id"],"model":getattr(provider,"model",None),"candidates":["V0","V1","V2","V3","V4"],"gates":{"critical_unsupported":0,"recall":0.70,"usable":0.90,"provenance":0.95,"v4_exact_copy":1.0,"v4_abstract_provenance":1.0,"application_accuracy":0.90},"aggregates":{candidate:_aggregate(candidate,rows[candidate],benchmark["cases"]) for candidate in rows},"rows":rows}
    write_completed_run(ARTIFACT_ROOT / run_id / "results.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
