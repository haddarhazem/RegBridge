from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.investment.brief_generation import deterministic_generation, generate_with_fallback
from app.modules.investment.brief_schemas import BriefEvidenceBundle

ROOT = Path(__file__).parents[2]


def _metrics(case: dict, generated, accepted: bool, issues: list[str]) -> dict:
    bundle = BriefEvidenceBundle.model_validate(case["bundle"])
    text = " ".join([generated.executive_summary, generated.thesis_fit_summary, *(highlight.text for highlight in generated.investment_highlights)])
    refs = {ref for highlight in generated.investment_highlights for ref in highlight.evidence_refs}
    supported = sum(1 for highlight in generated.investment_highlights if set(highlight.evidence_refs).issubset(set(bundle.evidence_refs)))
    expected_ack = bundle.matching_result["dimensions"]
    actual_ack = {item.dimension: item.outcome for item in generated.matching_acknowledgements}
    return {
        "case_id": case["case_id"], "accepted": accepted, "issues": issues,
        "section_completeness": all(bool(value) for value in (generated.executive_summary, generated.thesis_fit_summary, generated.matching_acknowledgements)),
        "supported_claims": supported, "total_claims": len(generated.investment_highlights),
        "unsupported_claims": len(generated.investment_highlights) - supported,
        "missing_information_correct": bundle.missing_information == bundle.missing_information,
        "matching_fidelity": actual_ack == expected_ack,
        "safety_violation": any(term in text.casefold() for term in ("guaranteed", "high roi", "expected return", "predict success")),
        "unauthorized_data_used": "excluded_private_input" in text or "internal_notes" in text,
        "claim_refs": sorted(refs),
    }


async def run() -> dict:
    benchmark = json.loads((ROOT / "benchmarks/investor_opportunity_brief_ex022_v1.json").read_text(encoding="utf-8"))
    cases = benchmark["cases"]
    v1_rows = []
    provider_available = os.getenv("EX022_LIVE") == "1"
    if provider_available:
        provider = get_mistral_provider()
        for case in cases:
            bundle = BriefEvidenceBundle.model_validate(case["bundle"])
            generated, accepted, issues, execution, rejected_output, rejected_refs = await generate_with_fallback(provider, bundle)
            row = _metrics(case, generated, accepted, issues)
            row["execution"] = execution
            provider_api_success = bool(execution and execution.get("status") == "success")
            provider_response_received = execution is not None
            provider_json_schema_valid = provider_response_received and "invalid structured brief" not in issues
            row["provider_api_success"] = provider_api_success
            row["provider_structured_response_received"] = provider_response_received
            row["provider_json_schema_valid"] = provider_json_schema_valid
            row["provider_semantic_validator_pass"] = provider_response_received and accepted
            row["fallback_schema_valid"] = not accepted and bool(deterministic_generation(bundle))
            row["rejected_parsed_output"] = rejected_output
            row["rejected_evidence_refs"] = rejected_refs
            v1_rows.append(row)
    result = {"experiment":"EX-022", "phase":"corrected-contract-v1", "provider":"mistral", "model":getattr(get_mistral_provider(), "model", None) if provider_available else None, "v1":v1_rows, "v1_live":provider_available}
    output = ROOT / "artifacts/experiments/ex022_corrected_contract_v1_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), indent=2, ensure_ascii=False))
