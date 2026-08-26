from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.modules.ai.llm import LLMGenerationRequest, LLMMessage, LLMProvider
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.research.extraction_parser import ParsedSource, parse_source

from .contracts import EvidenceExtraction, EvidenceItem, EvidenceRef, FIELDS, StructuredExtraction, VerificationResult

ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks/research_extraction_ex024_v1.json"
RESULTS = ROOT / "artifacts/experiments/ex024_research_extraction_results.json"
PROMPT_VERSION = "ex024-v1"
SCHEMA_VERSION = "research-extraction-schema-v1"


def _schema(model: type) -> dict:
    return {"type": "json_schema", "json_schema": {"name": model.__name__, "schema": model.model_json_schema()}}


def _prompt(source: str, *, candidate: str, source_version_id: str, evidence: bool = False) -> list[LLMMessage]:
    rules = "Extract only explicit statements into domains, technologies, research_problem, methodology, main_results, explicit_applications, keywords, and limitations. Never infer applications, technology labels, results, TRL, patents, commercialization or human effectiveness. Use NOT_AVAILABLE when the source is silent."
    if evidence:
        rules += " Every SUPPORTED item must include source_version_id and a paragraph locator. Use the supplied source text only."
    return [
        LLMMessage(role="system", content=f"You are a bounded scientific extraction component. {rules} Return JSON only."),
        LLMMessage(role="user", content=f"CANDIDATE={candidate}\nSOURCE VERSION ID={source_version_id}\nSOURCE TEXT:\n{source}"),
    ]


async def _generate(provider: LLMProvider, messages: list[LLMMessage], schema: dict | None, operation: str):
    request = LLMGenerationRequest(messages=messages, temperature=0, max_tokens=1800, response_format=schema, prompt_version=PROMPT_VERSION, operation=operation)
    return await provider.generate(request)


def _loose_normalize(raw: dict) -> dict:
    result = {field: {"status": "NOT_AVAILABLE", "items": []} for field in (*FIELDS, "keywords")}
    for field in (*FIELDS, "keywords"):
        value = raw.get(field)
        if value is None or value == [] or value == "":
            continue
        values = value if isinstance(value, list) else [value]
        result[field] = {"status": "SUPPORTED", "items": [{"value": str(item)} for item in values if str(item).strip()]}
    result["regbridge_abstract"] = str(raw.get("regbridge_abstract", ""))[:1200]
    return result


def _parse_response(content: str, candidate: str):
    raw = json.loads(content)
    if candidate == "V0":
        return StructuredExtraction.model_validate(_loose_normalize(raw))
    return (StructuredExtraction if candidate == "V1" else EvidenceExtraction).model_validate(raw)


def _validate_evidence(extraction: EvidenceExtraction, parsed: ParsedSource, case_id: str) -> tuple[int, int]:
    valid = invalid = 0
    for field in FIELDS:
        current = getattr(extraction, field)
        for item in current.items:
            refs = {(ref.source_version_id, json.dumps(ref.locator, sort_keys=True)) for ref in item.evidence_refs}
            if len(refs) != len(item.evidence_refs):
                invalid += 1
                continue
            item_valid = False
            for ref in item.evidence_refs:
                try:
                    if ref.source_version_id != case_id:
                        raise ValueError("wrong source version")
                    parsed.resolve({**ref.locator, "document_version_id": ref.source_version_id})
                    item_valid = True
                except (ValueError, TypeError, KeyError):
                    continue
            if item_valid:
                valid += 1
            else:
                invalid += 1
    return valid, invalid


def _item_evidence_valid(item: EvidenceItem, parsed: ParsedSource, case_id: str) -> bool:
    refs = {(ref.source_version_id, json.dumps(ref.locator, sort_keys=True)) for ref in item.evidence_refs}
    if len(refs) != len(item.evidence_refs):
        return False
    for ref in item.evidence_refs:
        try:
            if ref.source_version_id != case_id:
                continue
            parsed.resolve({**ref.locator, "document_version_id": ref.source_version_id})
            return True
        except (ValueError, TypeError, KeyError):
            continue
    return False


def _prediction(extraction: StructuredExtraction | EvidenceExtraction) -> dict[str, list[str]]:
    return {field: [item.value for item in getattr(extraction, field).items] if getattr(extraction, field).status == "SUPPORTED" else [] for field in FIELDS}


def _gold(case: dict) -> dict[str, list[str]]:
    return case["gold"]


def _score(case: dict, predicted: dict[str, list[str]], *, evidence_valid: int = 0, evidence_invalid: int = 0) -> dict:
    gold = _gold(case)
    tp = fp = fn = 0
    details = []
    for field in FIELDS:
        expected = {value.casefold().strip() for value in gold.get(field, [])}
        actual = {value.casefold().strip() for value in predicted.get(field, [])}
        tp_values = actual & expected
        fp_values = actual - expected
        fn_values = expected - actual
        tp += len(tp_values); fp += len(fp_values); fn += len(fn_values)
        details.append({"field": field, "true_positive": sorted(tp_values), "unsupported": sorted(fp_values), "missed": sorted(fn_values)})
    critical_fields = {"technologies", "main_results", "explicit_applications"}
    critical_fp = sum(len(set(predicted.get(field, [])) - set(gold[field])) for field in critical_fields)
    return {"true_positive": tp, "unsupported": fp, "missed": fn, "evidence_valid": evidence_valid, "evidence_invalid": evidence_invalid, "critical_unsupported": critical_fp, "details": details}


async def evaluate_candidate(provider: LLMProvider, case: dict, candidate: str) -> dict:
    started = time.perf_counter()
    parsed = parse_source(case["case_id"], "text/plain", case["source_text"].encode())
    row: dict[str, Any] = {"case_id": case["case_id"], "candidate": candidate, "provider_success": False, "structured_valid": False, "provider_error": None}
    try:
        response = await _generate(provider, _prompt(parsed.text, candidate=candidate, source_version_id=case["case_id"], evidence=candidate in {"V2", "V3"}), _schema(StructuredExtraction if candidate == "V1" else EvidenceExtraction) if candidate in {"V1", "V2", "V3"} else None, f"ex024_{candidate.lower()}_extraction")
        row["provider_success"] = True
        row["execution"] = response.execution.model_dump(mode="json") if response.execution else None
        extraction = _parse_response(response.content, candidate)
        row["structured_valid"] = True
        evidence_valid = evidence_invalid = 0
        if candidate in {"V2", "V3"}:
            evidence_valid, evidence_invalid = _validate_evidence(extraction, parsed, case["case_id"])
            predicted = _prediction(extraction)
            if candidate == "V3":
                verified: dict[str, list[str]] = {field: [] for field in FIELDS}
                for field in FIELDS:
                    for item in getattr(extraction, field).items:
                        evidence_text = ""
                        if _item_evidence_valid(item, parsed, case["case_id"]):
                            evidence_text = parsed.resolve({**item.evidence_refs[0].locator, "document_version_id": case["case_id"]})
                        verifier = await _generate(provider, [LLMMessage(role="system", content="Judge only whether the claim is supported by the supplied evidence. Return JSON only with verdict SUPPORTED, UNSUPPORTED, or UNVERIFIABLE. Do not create claims."), LLMMessage(role="user", content=json.dumps({"field": field, "claim": item.value, "evidence": evidence_text}, ensure_ascii=False))], _schema(VerificationResult), "ex024_v3_verifier")
                        verdict = VerificationResult.model_validate(json.loads(verifier.content)).verdict
                        if verdict == "SUPPORTED":
                            verified[field].append(item.value)
                predicted = verified
        else:
            predicted = _prediction(extraction)
        row["score"] = _score(case, predicted, evidence_valid=evidence_valid, evidence_invalid=evidence_invalid)
        row["predicted"] = predicted
    except Exception as exc:
        row["provider_error"] = type(exc).__name__
        row["score"] = _score(case, {field: [] for field in FIELDS})
    row["latency_ms"] = (time.perf_counter() - started) * 1000
    return row


async def run(provider: LLMProvider | None = None) -> dict:
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    if len(benchmark["cases"]) < 15 or sum(len(case["gold"]) for case in benchmark["cases"]) < 100:
        raise RuntimeError("EX-024 benchmark gate failed")
    if not benchmark.get("frozen") or not benchmark.get("evidence_locator_policy"):
        raise RuntimeError("EX-024 benchmark is not frozen with a locator policy")
    provider = provider or get_mistral_provider()
    rows = {candidate: [await evaluate_candidate(provider, case, candidate) for case in benchmark["cases"]] for candidate in ("V0", "V1", "V2", "V3")}
    aggregates = {}
    for candidate, candidate_rows in rows.items():
        scores = [row["score"] for row in candidate_rows]
        generated = sum(score["true_positive"] + score["unsupported"] for score in scores)
        expected = sum(score["true_positive"] + score["missed"] for score in scores)
        executions = [row.get("execution") or {} for row in candidate_rows]
        generated_denominator = generated or 1
        application_cases = sum(1 for case in benchmark["cases"] if case["gold"]["explicit_applications"] or True)
        application_correct = sum(1 for case, row in zip(benchmark["cases"], candidate_rows) if {v.casefold().strip() for v in row.get("predicted", {}).get("explicit_applications", [])} == {v.casefold().strip() for v in case["gold"]["explicit_applications"]})
        aggregates[candidate] = {
            "denominators": {"generated_claims": generated, "gold_supported_items": expected, "application_cases": application_cases},
            "evidence_precision": sum(s["true_positive"] for s in scores) / generated if generated else 0,
            "unsupported_claim_rate": sum(s["unsupported"] for s in scores) / generated if generated else 0,
            "extraction_recall": sum(s["true_positive"] for s in scores) / expected if expected else 0,
            "provenance_coverage": sum(s["evidence_valid"] for s in scores) / generated if generated and candidate in {"V2", "V3"} else None,
            "structured_validity": sum(row["structured_valid"] for row in candidate_rows) / len(candidate_rows),
            "explicit_application_accuracy": application_correct / application_cases,
            "critical_unsupported": sum(s["critical_unsupported"] for s in scores),
            "numeric_mutations": sum(1 for row in candidate_rows for detail in row["score"]["details"] if detail["field"] == "main_results" and detail["unsupported"] and any(any(ch.isdigit() for ch in value) for value in detail["unsupported"])),
            "negation_errors": sum(1 for row in candidate_rows if any("no significant improvement" in value.casefold() for value in row.get("predicted", {}).get("main_results", [])) and "no significant improvement with the tested compound" not in row.get("predicted", {}).get("main_results", [])),
            "provider_success": sum(row["provider_success"] for row in candidate_rows) / len(candidate_rows),
            "latency_ms_avg": statistics.mean(row["latency_ms"] for row in candidate_rows),
            "input_tokens": sum(e.get("prompt_tokens", 0) or 0 for e in executions) or None,
            "output_tokens": sum(e.get("completion_tokens", 0) or 0 for e in executions) or None,
            "cost": sum(e.get("estimated_cost", 0) or 0 for e in executions) or None,
        }
    result = {"experiment": "EX-024", "research_question": "RQ-024", "benchmark_id": benchmark["benchmark_id"], "candidate_versions": ["V0", "V1", "V2", "V3"], "provider": "mistral", "model": getattr(provider, "model", None), "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION, "aggregates": aggregates, "rows": rows}
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
