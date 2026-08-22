"""Structural checks for the human-reviewable EX-003 benchmark."""

from __future__ import annotations

from typing import Any


SUPPORT_LABELS = {"supported", "partially_supported", "unsupported", "contradicted", "not_applicable"}
VERDICTS = {"pass", "pass_with_warnings", "block"}


def validate_rows(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids = [row.get("id") for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("duplicate case IDs")
    for row in rows:
        case_id = row.get("id", "<missing>")
        evidence_ids = {item.get("evidence_id") for item in row.get("evidence", [])}
        if row.get("annotation_status") not in {"needs_human_validation", "human_validated"}:
            errors.append(f"{case_id}: invalid annotation status")
        if row.get("expected_verdict") is not None and row.get("expected_verdict") not in VERDICTS:
            errors.append(f"{case_id}: invalid expected verdict")
        for field in ("expected_public_source_correct", "expected_citation_resolution_correct"):
            if row.get(field) not in {None, True, False}:
                errors.append(f"{case_id}: invalid {field}")
        for claim in row.get("claims", []):
            claim_id = claim.get("claim_id", "<missing>")
            if claim.get("proposed_support") not in SUPPORT_LABELS:
                errors.append(f"{case_id}/{claim_id}: invalid proposed support")
            if not set(claim.get("proposed_evidence_ids", [])) <= evidence_ids:
                errors.append(f"{case_id}/{claim_id}: proposed evidence does not resolve")
            if claim.get("expected_support") is not None and claim.get("expected_support") not in SUPPORT_LABELS:
                errors.append(f"{case_id}/{claim_id}: invalid expected support")
            if not set(claim.get("expected_evidence_ids", [])) <= evidence_ids:
                errors.append(f"{case_id}/{claim_id}: expected evidence does not resolve")
    return errors
