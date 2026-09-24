"""Deterministic, explainable contract-review risk index.

The index is a navigation aid for structured contract findings. It is not a
legal-validity, compliance, or signability assessment.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field


_SEVERITY_POINTS = {
    "informational": 0,
    "unknown": 0,
    "low": 0,
    "medium": 2,
    "high": 4,
    "critical": 6,
}


class ContractRiskIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "Indice de risque contractuel"
    score: int = Field(ge=0, le=100)
    range_max: int = 100
    formula: str
    severity_points: int = Field(ge=0)
    missing_clause_count: int = Field(ge=0)
    contradiction_count: int = Field(ge=0)
    contributors: list[str] = Field(default_factory=list, max_length=40)
    limitation: str = (
        "Indice de revue fond\u00e9 sur les constats structur\u00e9s ; il ne constitue pas un avis juridique "
        "ni une d\u00e9cision de signature."
    )


def calculate_contract_risk_index(clauses: Iterable[object]) -> ContractRiskIndex:
    """Calculate a bounded review index from persisted clause findings only.

    Only verified, material findings can contribute. A normal FOUND/low clause
    has zero contribution because its presence is not a contractual problem.
    Verified medium/high/critical issues use 2/4/6 points; verified missing
    provisions and contradictions each add two review points. The result is
    doubled and capped at 100.
    """

    severity_points = 0
    missing_count = 0
    contradiction_count = 0
    contributors: list[str] = []
    for clause in clauses:
        level = str(getattr(clause, "risk_level", "unknown") or "unknown").lower()
        status = str(getattr(clause, "status", "FOUND") or "FOUND").upper()
        title = str(
            getattr(clause, "title", None)
            or getattr(clause, "heading", None)
            or getattr(clause, "clause_type", None)
            or "Clause analys\u00e9e"
        )
        verification = str(getattr(clause, "verification_status", "UNVERIFIED") or "UNVERIFIED").upper()
        material = status in {"MISSING", "AMBIGUOUS", "CONTRADICTORY"} or bool(getattr(clause, "issues", []))
        if verification != "VERIFIED" or not material:
            continue
        points = _SEVERITY_POINTS.get(level, 0)
        severity_points += points
        if points:
            contributors.append(f"{title} : niveau {level} (+{points})")
        if status == "MISSING":
            missing_count += 1
            contributors.append(f"{title} : disposition non d\u00e9tect\u00e9e (+2)")
        elif status == "CONTRADICTORY":
            contradiction_count += 1
            contributors.append(f"{title} : incoh\u00e9rence potentielle (+2)")

    score = min(100, 2 * (severity_points + (2 * missing_count) + (2 * contradiction_count)))
    return ContractRiskIndex(
        score=score,
        formula=(
            "Seuls les constats verifies contribuent : 0/0/2/4/6 points selon le niveau "
            "informationnel/faible/moyen/eleve/critique, +2 par disposition non detectee, "
            "+2 par incoherence, total x2 plafonne a 100."
        ),
        severity_points=severity_points,
        missing_clause_count=missing_count,
        contradiction_count=contradiction_count,
        contributors=contributors,
    )
