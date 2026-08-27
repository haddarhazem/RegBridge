import hashlib
import json
from pathlib import Path


BENCHMARK = Path(__file__).resolve().parents[4] / "benchmarks" / "prompt_injection_ex027_v1.json"


def test_ex027_benchmark_is_frozen_and_complete():
    raw = BENCHMARK.read_bytes()
    cases = json.loads(raw)
    assert len(cases) == 48
    assert len({case["case_id"] for case in cases}) == 48
    assert sum(case["split"] == "DEV" for case in cases) == 32
    assert sum(case["split"] == "HOLDOUT" for case in cases) == 16
    assert hashlib.sha256(raw).hexdigest()
    assert all(case["forbidden_sentinels"] is not None for case in cases)


def test_ex027_contains_required_attack_taxonomy_and_benign_controls():
    cases = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    categories = {case["category"] for case in cases}
    assert {"DIRECT_USER_INJECTION", "INDIRECT_RAG_INJECTION", "DOCUMENT_INJECTION", "TOOL_OUTPUT_INJECTION", "ROLE_IMPERSONATION", "CROSS_USER_ACCESS", "VISIBILITY_OVERRIDE", "GRANT_SCOPE_ESCALATION", "SYSTEM_POLICY_EXFILTRATION", "MULTILINGUAL", "MULTI_TURN", "BENIGN_CONTROL"} <= categories
    assert sum(case["benign"] for case in cases) >= 8
