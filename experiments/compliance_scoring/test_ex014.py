from experiments.compliance_scoring.run_ex014 import score

def test_unweighted_semantics():
    controls=[{"id":"a","status":"SATISFIED","applicability":"APPLICABLE","evidence":["e"]},{"id":"b","status":"SATISFIED","applicability":"NOT_APPLICABLE","evidence":["e"]},{"id":"c","status":"SATISFIED","applicability":"APPLICABLE","evidence":["e:REVOKED"]}]
    result=score(controls)
    assert result["score"] == "50.00" and result["excluded"] == ["b"] and result["contributing"] == ["a"]

def test_zero_eligible_is_unavailable():
    assert score([{"id":"a","status":"SATISFIED","applicability":"NOT_APPLICABLE","evidence":["e"]}])["score"] is None

def test_secondary_evidence_is_stable():
    base=[{"id":"a","status":"SATISFIED","applicability":"APPLICABLE","evidence":["e"]}]
    assert score(base)["score"] == score([{**base[0],"evidence":["e","e2"]}])["score"]
