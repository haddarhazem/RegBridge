"""Deterministic V0 factual verification against a frozen brief run."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.modules.investment.brief_verification_schemas import ClaimVerdict


VERIFIER_STRATEGY = "deterministic_first_semantic_fallback"
VERIFIER_VERSION = "1"
_NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class ClaimDecision:
    claim_id: str
    section: str
    claim_text: str
    claim_type: str
    verdict: ClaimVerdict
    reason_code: str
    evidence_refs: list[str]


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    match = _NUMBER.search(str(value).replace("€", "").replace(",", "").replace(" ", ""))
    return float(match.group().replace(",", ".")) if match else None


def _same_value(left: Any, right: Any) -> bool:
    left_number, right_number = _number(left), _number(right)
    if left_number is not None and right_number is not None:
        return left_number == right_number
    return str(left).strip().casefold() == str(right).strip().casefold()


def _fact_values(bundle: dict) -> dict[str, list[tuple[Any, str]]]:
    values: dict[str, list[tuple[Any, str]]] = {}
    for fact in bundle.get("confirmed_facts", []):
        if fact.get("status") in {"confirmed", "corrected"} and fact.get("domain") and fact.get("evidence_ref"):
            values.setdefault(str(fact["domain"]), []).append((fact.get("value"), str(fact["evidence_ref"])))
    return values


def _highlight_decision(index: int, claim: dict, bundle: dict) -> ClaimDecision:
    text = str(claim.get("text", ""))
    refs = [str(ref) for ref in claim.get("evidence_refs", [])]
    allowed = set(bundle.get("evidence_refs", []))
    if not refs or not set(refs).issubset(allowed):
        return ClaimDecision(f"highlight-{index}", "Key Investment Highlights", text, "structured_fact", "UNSUPPORTED", "evidence_ref_not_authorized", refs)
    if ":" not in text:
        return ClaimDecision(f"highlight-{index}", "Key Investment Highlights", text, "structured_fact", "UNVERIFIABLE", "claim_not_structured", refs)
    domain, value = (part.strip() for part in text.split(":", 1))
    matches = any(_same_value(candidate, value) and ref in refs for candidate, ref in _fact_values(bundle).get(domain, []))
    if matches:
        return ClaimDecision(f"highlight-{index}", "Key Investment Highlights", text, "structured_fact", "SUPPORTED", "exact_confirmed_fact", refs)
    return ClaimDecision(f"highlight-{index}", "Key Investment Highlights", text, "structured_fact", "UNSUPPORTED", "fact_value_not_supported", refs)


def _matching_decision(index: int, text: str, bundle: dict) -> ClaimDecision:
    claim_id = f"matching-{index}"
    refs = [ref for ref in bundle.get("evidence_refs", []) if ref.startswith("matching:")]
    if ":" not in text:
        return ClaimDecision(claim_id, "Why This Startup Fits Your Thesis", text, "matching_outcome", "UNVERIFIABLE", "claim_not_structured", refs)
    dimension, outcome = (part.strip() for part in text.split(":", 1))
    expected = (bundle.get("matching_result", {}).get("dimensions") or {}).get(dimension)
    if expected is None:
        return ClaimDecision(claim_id, "Why This Startup Fits Your Thesis", text, "matching_outcome", "UNSUPPORTED", "unknown_matching_dimension", refs)
    if outcome != expected:
        return ClaimDecision(claim_id, "Why This Startup Fits Your Thesis", text, "matching_outcome", "UNSUPPORTED", "matching_outcome_changed", refs)
    return ClaimDecision(claim_id, "Why This Startup Fits Your Thesis", text, "matching_outcome", "SUPPORTED", "canonical_matching_result", refs)


def verify_frozen_brief(content: dict, evidence_bundle: dict, matching_result: dict) -> list[ClaimDecision]:
    bundle = dict(evidence_bundle)
    bundle["matching_result"] = matching_result
    decisions = [_matching_decision(index, text, bundle) for index, text in enumerate(content.get("thesis_fit", []))]
    claims = content.get("claims", [])
    if claims:
        decisions.extend(_highlight_decision(index, claim, bundle) for index, claim in enumerate(claims))
    else:
        decisions.extend(
            ClaimDecision(f"highlight-{index}", "Key Investment Highlights", text, "structured_fact", "UNVERIFIABLE", "claim_evidence_missing", [])
            for index, text in enumerate(content.get("investment_highlights", []))
        )
    return decisions
