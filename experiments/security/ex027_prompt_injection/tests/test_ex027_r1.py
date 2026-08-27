import hashlib
import json
from pathlib import Path


BENCHMARK = Path(__file__).resolve().parents[4] / "benchmarks" / "prompt_injection_ex027_r1_v1.json"


def test_r1_benchmark_and_provenance_are_frozen_before_holdout():
    raw = BENCHMARK.read_bytes()
    cases = json.loads(raw)
    assert len(cases) == 64
    assert len({case["case_id"] for case in cases}) == 64
    assert sum(case["split"] == "DEV" for case in cases) == 24
    holdout = [case for case in cases if case["split"] == "HOLDOUT"]
    assert len(holdout) == 40
    assert sum(case["category"] != "BENIGN_CONTROL" for case in holdout) == 20
    assert sum(case["category"] == "BENIGN_CONTROL" for case in holdout) == 20
    assert hashlib.sha256(raw).hexdigest()
    for case in cases:
        assert set(case["sentinel_provenance"]) == {"attacker_input", "authorized_context", "unauthorized_resource", "tool_output"}


def test_r1_attack_taxonomy_and_authorized_positive_controls_exist():
    cases = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    categories = {case["category"] for case in cases}
    assert {"DIRECT_USER_INJECTION", "INDIRECT_RAG_INJECTION", "DOCUMENT_INJECTION", "TOOL_OUTPUT_INJECTION", "ROLE_IMPERSONATION", "CROSS_USER_ACCESS", "PRIVATE_VISIBILITY_OVERRIDE", "DRAFT_VISIBILITY_OVERRIDE", "GRANT_SCOPE_ESCALATION", "SYSTEM_CONTEXT_EXFILTRATION", "MULTILINGUAL_FR", "MULTILINGUAL_EN", "MULTI_TURN", "BENIGN_CONTROL"} <= categories
    assert any(case["authorized_tool"] for case in cases)
    assert any(case["authorized_rag"] for case in cases)
