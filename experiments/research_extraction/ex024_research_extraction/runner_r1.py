"""EX-024-R1 runner with version-scoped allowlisted evidence IDs.

This module is deliberately separate from the initial diagnostic runner so the
first experiment's result path and accounting remain auditable.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

from app.modules.ai.llm import LLMGenerationRequest, LLMMessage, LLMProvider
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.research.extraction_parser import ParsedSource, SourceSegment, parse_source, resolve_segment, segment_source

from .contracts import EvidenceIdExtraction, FIELDS, StructuredExtraction, VerificationResult
from .runner import _gold, _loose_normalize, _score

ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks/research_extraction_ex024_v1.json"
RESULTS = ROOT / "artifacts/experiments/ex024_research_extraction_r1_results.json"
PROMPT_VERSION = "ex024-r1-v1"
SCHEMA_VERSION = "research-extraction-r1-schema-v1"
SEGMENTER_VERSION = "paragraph-segmenter-v1"


def _schema(model: type) -> dict:
    return {"type": "json_schema", "json_schema": {"name": model.__name__, "schema": model.model_json_schema()}}


def _prompt(source: str, segments: tuple[SourceSegment, ...], candidate: str, *, evidence: bool) -> list[LLMMessage]:
    rules = ("Extract only explicit statements into the requested fields. Use NOT_AVAILABLE when the source is silent. "
             "Do not infer applications, technologies, results, TRL, IP, commercialization, causality, scope, or human effectiveness.")
    if evidence:
        rules += " For every SUPPORTED item return one or more evidence_ids copied exactly from the allowlist. Never create offsets or IDs."
    allowlist = "\n".join(f"[{s.segment_id}] {s.text}" for s in segments)
    return [
        LLMMessage(role="system", content=f"You are a bounded scientific extraction component. {rules} Return JSON only."),
        LLMMessage(role="user", content=f"CANDIDATE={candidate}\nSOURCE VERSION ID={segments[0].document_version_id}\nSOURCE SEGMENTS:\n{allowlist}\nFULL SOURCE:\n{source}"),
    ]


async def _generate(provider: LLMProvider, messages: list[LLMMessage], schema: dict | None, operation: str):
    return await provider.generate(LLMGenerationRequest(messages=messages, temperature=0, max_tokens=1800, response_format=schema, prompt_version=PROMPT_VERSION, operation=operation))


def _prediction(extraction: StructuredExtraction | EvidenceIdExtraction) -> dict[str, list[str]]:
    return {field: [item.value for item in getattr(extraction, field).items] if getattr(extraction, field).status == "SUPPORTED" else [] for field in FIELDS}


def _evidence_stats(extraction: EvidenceIdExtraction, segments: tuple[SourceSegment, ...], case_id: str) -> tuple[int, int, dict[str, list[str]], list[str]]:
    valid = invalid = 0
    texts: dict[str, list[str]] = {}
    valid_values: list[dict[str, str]] = []
    allowed = {segment.segment_id for segment in segments}
    for field in FIELDS:
        current = getattr(extraction, field)
        for item in current.items:
            ids = list(dict.fromkeys(item.evidence_ids))
            if any(evidence_id not in allowed for evidence_id in ids):
                invalid += 1
                continue
            try:
                resolved = [resolve_segment(segments, evidence_id, case_id) for evidence_id in ids]
            except ValueError:
                invalid += 1
                continue
            valid += 1
            valid_values.append({"field": field, "value": item.value})
            texts[f"{field}:{item.value}"] = [segment.text for segment in resolved]
    return valid, invalid, texts, valid_values


async def evaluate_candidate(provider: LLMProvider, case: dict[str, Any], candidate: str) -> dict[str, Any]:
    started = time.perf_counter()
    parsed = parse_source(case["case_id"], "text/plain", case["source_text"].encode())
    segments = segment_source(parsed)
    row: dict[str, Any] = {"case_id": case["case_id"], "candidate": candidate, "provider_success": False, "structured_valid": False, "parse_success": False, "provider_error": None, "verification": {"calls": 0, "provider_success": 0, "structured_valid": 0, "supported": 0, "unsupported": 0, "unverifiable": 0}, "verification_executions": []}
    try:
        model = EvidenceIdExtraction if candidate in {"V2", "V3"} else StructuredExtraction
        response = await _generate(provider, _prompt(parsed.text, segments, candidate, evidence=candidate in {"V2", "V3"}), _schema(model) if candidate != "V0" else None, f"ex024_r1_{candidate.lower()}_extraction")
        row["provider_success"] = True
        row["raw_provider_content"] = response.content
        row["extraction_execution"] = response.execution.model_dump(mode="json") if response.execution else None
        raw = json.loads(response.content)
        row["parse_success"] = True
        extraction = model.model_validate(_loose_normalize(raw) if candidate == "V0" else raw)
        row["structured_valid"] = candidate == "V0" or True
        evidence_valid = evidence_invalid = 0
        evidence_texts: dict[str, list[str]] = {}
        evidence_valid_values: list[str] = []
        if candidate in {"V2", "V3"}:
            evidence_valid, evidence_invalid, evidence_texts, evidence_valid_values = _evidence_stats(extraction, segments, case["case_id"])
        predicted = _prediction(extraction)
        if candidate == "V3":
            verified = {field: [] for field in FIELDS}
            evidence_valid_values = []
            for field in FIELDS:
                for item in getattr(extraction, field).items:
                    key = f"{field}:{item.value}"
                    if key not in evidence_texts:
                        row["verification"]["unverifiable"] += 1
                        continue
                    row["verification"]["calls"] += 1
                    try:
                        verifier = await _generate(provider, [LLMMessage(role="system", content="Judge only whether this claim is supported by the supplied evidence. Return JSON only with verdict SUPPORTED, UNSUPPORTED, or UNVERIFIABLE. Do not create or edit claims."), LLMMessage(role="user", content=json.dumps({"field": field, "claim": item.value, "evidence": evidence_texts[key]}, ensure_ascii=False))], _schema(VerificationResult), "ex024_r1_v3_verifier")
                        row["verification"]["provider_success"] += 1
                        if verifier.execution:
                            row["verification_executions"].append(verifier.execution.model_dump(mode="json"))
                        result = VerificationResult.model_validate(json.loads(verifier.content))
                        row["verification"]["structured_valid"] += 1
                        row["verification"][result.verdict.casefold()] += 1
                        if result.verdict == "SUPPORTED":
                            verified[field].append(item.value)
                            evidence_valid_values.append({"field": field, "value": item.value})
                    except Exception:
                        row["verification"]["unverifiable"] += 1
            predicted = verified
        row["score"] = _score(case, predicted, evidence_valid=evidence_valid, evidence_invalid=evidence_invalid)
        row["predicted"] = predicted
        row["evidence_valid_values"] = evidence_valid_values
    except Exception as exc:
        row["provider_error"] = type(exc).__name__
        row["score"] = _score(case, {field: [] for field in FIELDS})
    row["latency_ms"] = (time.perf_counter() - started) * 1000
    return row


async def run(provider: LLMProvider | None = None) -> dict[str, Any]:
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    if not benchmark.get("frozen") or len(benchmark["cases"]) != 15 or sum(len(case["gold"]) for case in benchmark["cases"]) != 105:
        raise RuntimeError("EX-024-R1 frozen benchmark gate failed")
    provider = provider or get_mistral_provider()
    rows = {candidate: [await evaluate_candidate(provider, case, candidate) for case in benchmark["cases"]] for candidate in ("V0", "V1", "V2", "V3")}
    aggregates: dict[str, Any] = {}
    for candidate, candidate_rows in rows.items():
        scores = [row["score"] for row in candidate_rows]
        generated = sum(score["true_positive"] + score["unsupported"] for score in scores)
        expected = sum(score["true_positive"] + score["missed"] for score in scores)
        evidence_required = sum(score["evidence_valid"] + score["evidence_invalid"] for score in scores)
        accepted = sum(score["true_positive"] for score in scores)
        evidence_valid_correct = sum(1 for row, case in zip(candidate_rows, benchmark["cases"]) for item in row.get("evidence_valid_values", []) if item["value"].casefold().strip() in {value.casefold().strip() for value in _gold(case).get(item["field"], [])})
        executions = [row.get("extraction_execution") or {} for row in candidate_rows]
        verification_executions = [execution for row in candidate_rows for execution in row.get("verification_executions", [])]
        verification = [row["verification"] for row in candidate_rows]
        verifier_calls = sum(item["calls"] for item in verification)
        verifier_decisions = sum(item["supported"] + item["unsupported"] + item["unverifiable"] for item in verification)
        aggregates[candidate] = {
            "denominators": {"generated_claims": generated, "gold_supported_items": expected, "evidence_required": evidence_required, "verifier_decisions": verifier_decisions},
            "provider_success": f"{sum(row['provider_success'] for row in candidate_rows)}/{len(candidate_rows)}",
            "structured_validity": f"{sum(row['structured_valid'] for row in candidate_rows)}/{len(candidate_rows)}",
            "usable_conclusive_rate": f"{sum(bool(row.get('predicted')) for row in candidate_rows)}/{len(candidate_rows)}",
            "claim_precision": f"{sum(score['true_positive'] for score in scores)}/{generated}" if generated else "0/0",
            "unsupported_claim_rate": f"{sum(score['unsupported'] for score in scores)}/{generated}" if generated else "0/0",
            "extraction_recall": f"{sum(score['true_positive'] for score in scores)}/{expected}",
            "evidence_ref_validity": f"{sum(score['evidence_valid'] for score in scores)}/{evidence_required}" if evidence_required else None,
            "evidence_entailment_precision": f"{evidence_valid_correct}/{sum(len(row.get('evidence_valid_values', [])) for row in candidate_rows)}" if candidate in {"V2", "V3"} and sum(len(row.get("evidence_valid_values", [])) for row in candidate_rows) else None,
            "provenance_coverage": f"{evidence_valid_correct}/{accepted}" if accepted and candidate in {"V2", "V3"} else None,
            "critical_unsupported": sum(score["critical_unsupported"] for score in scores),
            "numeric_mutations": sum(1 for score in scores for detail in score["details"] if detail["field"] == "main_results" and detail["unsupported"] and any(any(ch.isdigit() for ch in value) for value in detail["unsupported"])),
            "negation_errors": sum(1 for case, row in zip(benchmark["cases"], candidate_rows) if any("no significant improvement" in value.casefold() for value in case["gold"]["main_results"]) and any("significant improvement" in value.casefold() and "no significant" not in value.casefold() for value in row.get("predicted", {}).get("main_results", []))),
            "abstention_rate": f"{sum(item['unverifiable'] for item in verification)}/{verifier_decisions}" if candidate == "V3" and verifier_decisions else None,
            "avg_latency_ms": statistics.mean(row["latency_ms"] for row in candidate_rows),
            "input_tokens": sum(item.get("prompt_tokens", 0) or 0 for item in executions) or None,
            "output_tokens": sum(item.get("completion_tokens", 0) or 0 for item in executions) or None,
            "v3_extraction_calls": len(candidate_rows) if candidate == "V3" else None,
            "v3_verifier_calls": verifier_calls if candidate == "V3" else None,
            "v3_verifier_provider_success": sum(item["provider_success"] for item in verification) if candidate == "V3" else None,
            "v3_verifier_structured_valid": sum(item["structured_valid"] for item in verification) if candidate == "V3" else None,
            "v3_avg_verification_latency_ms": statistics.mean(item.get("duration_ms", 0) for item in verification_executions) if candidate == "V3" and verification_executions else None,
            "v3_verifier_input_tokens": sum(item.get("prompt_tokens", 0) or 0 for item in verification_executions) if candidate == "V3" else None,
            "v3_verifier_output_tokens": sum(item.get("completion_tokens", 0) or 0 for item in verification_executions) if candidate == "V3" else None,
        }
    result = {"experiment": "EX-024-R1", "research_question": "RQ-024", "initial_run_preserved": True, "benchmark_id": benchmark["benchmark_id"], "model": getattr(provider, "model", None), "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION, "segmenter_version": SEGMENTER_VERSION, "utility_gates": {"recall": 0.70, "usable_conclusive": 0.90, "structured_validity": 0.90, "provenance": 0.95}, "aggregates": aggregates, "rows": rows}
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
