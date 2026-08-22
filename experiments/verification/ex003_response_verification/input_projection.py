"""Leakage-safe projection from a benchmark row to verifier input."""

from __future__ import annotations

from typing import Any

from .contracts import VerificationInput


_ALLOWED = frozenset({
    "question", "answer", "public_sources", "cited_evidence_ids", "claims", "evidence",
})
_FORBIDDEN = frozenset({
    "expected_verdict", "expected_support", "expected_evidence_ids", "category",
    "mutation_type", "annotation_notes", "annotation_status",
})


def project_verifier_input(row: dict[str, Any]) -> VerificationInput:
    """Drop all human labels and benchmark metadata before inference."""

    projected = {key: row[key] for key in _ALLOWED if key in row}
    projected["claims"] = [
        {key: claim[key] for key in ("claim_id", "text", "material")}
        for claim in row.get("claims", [])
    ]
    projected["evidence"] = [
        {**evidence, "content": evidence["content"][:12000]}
        for evidence in row.get("evidence", [])
    ]
    return VerificationInput.model_validate(projected)


def forbidden_fields() -> frozenset[str]:
    return _FORBIDDEN
