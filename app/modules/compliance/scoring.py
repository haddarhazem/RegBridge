"""Pure deterministic compliance maturity scoring domain logic."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

METHOD_KEY = "compliance-maturity-unweighted"
METHOD_VERSION = "v1"
EVIDENCE_POLICY_VERSION = "active-evidence-required-v1"
ROUNDING_POLICY = "Decimal-half-up-2dp"

@dataclass(frozen=True)
class ScoringControl:
    id: str
    definition_id: str
    framework_version_id: str
    stable_key: str
    title: str
    status: str
    applicability: str
    evidence: tuple[dict[str, Any], ...]

def calculate(controls: list[ScoringControl]) -> dict[str, Any]:
    eligible = [c for c in controls if c.applicability != "NOT_APPLICABLE"]
    excluded = [c for c in controls if c.applicability == "NOT_APPLICABLE"]
    def active_evidence(control: ScoringControl) -> list[dict[str, Any]]:
        return [e for e in control.evidence if e["status"] == "ACTIVE"]
    evidenced = [c for c in eligible if active_evidence(c)]
    contributing = [c for c in eligible if c.status == "SATISFIED" and active_evidence(c)]
    declared_without_evidence = [c for c in eligible if c.status == "SATISFIED" and not active_evidence(c)]
    missing = [c for c in eligible if c not in contributing and c not in declared_without_evidence]
    denominator = len(eligible)
    numerator = len(contributing)
    score = None if denominator == 0 else (Decimal(numerator) / Decimal(denominator) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    coverage = None if denominator == 0 else (Decimal(len(evidenced)) / Decimal(denominator) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    def item(c: ScoringControl) -> dict[str, Any]:
        return {"project_control_id": c.id, "control_definition_id": c.definition_id, "stable_key": c.stable_key, "title": c.title, "status": c.status, "applicability": c.applicability}
    return {
        "numerator": numerator, "denominator": denominator, "score": None if score is None else float(score), "evidence_coverage": None if coverage is None else float(coverage),
        "eligible_controls": [item(c) for c in eligible], "satisfied": [item(c) for c in contributing], "missing": [item(c) for c in missing],
        "declared_satisfied_insufficiently_evidenced": [item(c) for c in declared_without_evidence], "not_applicable": [item(c) for c in excluded],
        "evidence_used": [{"project_control_id": c.id, "evidence_ids": [e["id"] for e in active_evidence(c)]} for c in contributing],
        "limitations": ["This is a maturity indicator, not legal certification, regulator approval, legal probability, or a guarantee of compliance."] + (["No applicable controls available for this scoring method."] if denominator == 0 else []),
    }
