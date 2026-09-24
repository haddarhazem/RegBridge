"""Deterministic contract-risk index coverage."""

from __future__ import annotations

from app.modules.documents.contract_analysis import ClauseAnalysis
from app.modules.documents.contract_risk import calculate_contract_risk_index


def _clause(*, title: str, status: str, risk_level: str) -> ClauseAnalysis:
    return ClauseAnalysis(
        clause_type=title.casefold().replace(" ", "_"),
        title=title,
        status=status,
        risk_level=risk_level,
        source_text="Synthetic source." if status != "MISSING" else "",
        source_location="Synthetic section" if status != "MISSING" else None,
        verification_status="VERIFIED",
        plain_language_summary="Synthetic structured finding.",
        purpose="Tests the deterministic formula.",
    )


def test_contract_risk_index_is_derived_from_structured_findings_and_explains_each_factor():
    clauses = [
        _clause(title="Liability", status="AMBIGUOUS", risk_level="high"),
        _clause(title="Termination", status="MISSING", risk_level="medium"),
        _clause(title="Duration", status="CONTRADICTORY", risk_level="high"),
        _clause(title="Payment", status="AMBIGUOUS", risk_level="medium"),
    ]

    index = calculate_contract_risk_index(clauses)
    severity = {"informational": 0, "unknown": 0, "low": 0, "medium": 2, "high": 4, "critical": 6}
    expected_severity = sum(severity[clause.risk_level] for clause in clauses)
    expected_missing = sum(clause.status == "MISSING" for clause in clauses)
    expected_contradictions = sum(clause.status == "CONTRADICTORY" for clause in clauses)

    assert index.severity_points == expected_severity
    assert index.missing_clause_count == expected_missing
    assert index.contradiction_count == expected_contradictions
    assert index.score == min(100, 2 * (expected_severity + (2 * expected_missing) + (2 * expected_contradictions)))
    assert any("Termination" in contributor and "+2" in contributor for contributor in index.contributors)
    assert any("Duration" in contributor and "+2" in contributor for contributor in index.contributors)
    assert "0/0/2/4/6" in index.formula
    assert "signature" in index.limitation.casefold()
