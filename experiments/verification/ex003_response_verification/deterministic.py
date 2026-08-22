"""V1 deterministic provenance and citation checks.

V1 intentionally does not claim semantic entailment from prose.
"""

from .contracts import VerificationInput, VerificationOutput


def verify_structure(item: VerificationInput) -> VerificationOutput:
    evidence_ids = {evidence.evidence_id for evidence in item.evidence}
    issues: list[str] = []
    if not evidence_ids:
        issues.append("no evidence supplied")
    if len(evidence_ids) != len(item.evidence):
        issues.append("duplicate evidence IDs")
    missing_citations = sorted(set(item.cited_evidence_ids) - evidence_ids)
    if missing_citations:
        issues.append("unresolved evidence IDs: " + ", ".join(missing_citations))
    organizations = {evidence.organization for evidence in item.evidence}
    missing_sources = sorted(set(item.public_sources) - organizations)
    if missing_sources:
        issues.append("public sources absent from evidence: " + ", ".join(missing_sources))
    verdict = "block" if issues else "pass"
    return VerificationOutput(
        claims=[],
        citation_issues=issues,
        verdict=verdict,
        reasons=["deterministic provenance checks only; semantic support is not evaluated"],
    )
