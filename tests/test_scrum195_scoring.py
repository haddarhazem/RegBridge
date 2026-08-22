import uuid
import pytest
from app.modules.compliance.scoring import calculate, ScoringControl

def c(key, status="NOT_STARTED", applicability="APPLICABLE", evidence=()):
    return ScoringControl(str(uuid.uuid4()), str(uuid.uuid4()), "v1", key, key, status, applicability, tuple({"id": x, "status": "ACTIVE"} for x in evidence))

def test_deterministic_explainable_unweighted_score():
    controls=[c("a","SATISFIED",evidence=("e1",)), c("b","NOT_SATISFIED"), c("c","IN_PROGRESS"), c("na","SATISFIED","NOT_APPLICABLE",("e2",))]
    first=calculate(controls); second=calculate(controls)
    assert first == second and first["score"] == 33.33 and first["numerator"] == 1 and first["denominator"] == 3
    assert first["not_applicable"][0]["stable_key"] == "na" and first["evidence_used"][0]["evidence_ids"] == ["e1"]

def test_missing_evidence_and_revocation_do_not_satisfy():
    result=calculate([c("declared","SATISFIED"), c("revoked","SATISFIED",evidence=()), c("na","NOT_STARTED","NOT_APPLICABLE")])
    assert result["score"] == 0.0 and len(result["declared_satisfied_insufficiently_evidenced"]) == 2

def test_no_eligible_controls_is_unavailable():
    result=calculate([c("na","SATISFIED","NOT_APPLICABLE",("e",))])
    assert result["score"] is None and result["denominator"] == 0 and any("No applicable" in x for x in result["limitations"])

@pytest.mark.parametrize("status", ["NOT_STARTED", "IN_PROGRESS", "NOT_SATISFIED"])
def test_non_satisfied_statuses_contribute_zero(status):
    result = calculate([c("control", status, evidence=("e",))])
    assert result["numerator"] == 0 and result["score"] == 0.0

def test_evidence_coverage_is_not_maturity_score():
    result = calculate([c("satisfied", "SATISFIED", evidence=("e",)), c("missing", "SATISFIED")])
    assert result["score"] == 50.0 and result["evidence_coverage"] == 50.0
    assert result["satisfied"][0]["stable_key"] == "satisfied"

def test_overall_aggregation_is_control_weighted_not_percentage_averaged():
    controls = [c("gdpr", "SATISFIED", evidence=("g",))]
    controls += [c(f"ai-{i}", "NOT_SATISFIED") for i in range(9)]
    result = calculate(controls)
    assert result["score"] == 10.0 and result["denominator"] == 10

def test_explanation_has_reconstruction_fields_and_safety_limitations():
    result = calculate([c("control", "SATISFIED")])
    assert {"numerator", "denominator", "eligible_controls", "satisfied", "missing", "not_applicable", "evidence_used", "limitations"} <= result.keys()
    assert "legal certification" in result["limitations"][0]
