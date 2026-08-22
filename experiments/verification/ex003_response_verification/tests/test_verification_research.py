import json
from pathlib import Path

from experiments.verification.ex003_response_verification.contracts import VerificationInput
from experiments.verification.ex003_response_verification.deterministic import verify_structure
from experiments.verification.ex003_response_verification.input_projection import forbidden_fields, project_verifier_input
from experiments.verification.ex003_response_verification.validation import validate_rows
from experiments.verification.ex003_response_verification.prompt import build_request
from experiments.verification.ex003_response_verification.replay_v3 import cascade_verdict, evaluate, replay_predictions


def test_verifier_input_excludes_human_labels_and_mutation_metadata():
    row = {
        "question": "Question",
        "answer": "Réponse",
        "public_sources": ["CNIL"],
        "cited_evidence_ids": ["E1"],
        "claims": [{"claim_id": "C1", "text": "Claim", "material": True}],
        "evidence": [{"evidence_id": "E1", "organization": "CNIL", "source_domain": "www.cnil.fr", "content": "Evidence"}],
        "expected_verdict": "block",
        "expected_support": "unsupported",
        "category": "unsupported_material_claim",
        "mutation_type": "test",
        "annotation_status": "needs_human_validation",
    }
    projected = project_verifier_input(row)
    assert isinstance(projected, VerificationInput)
    assert not (set(projected.model_dump()) & forbidden_fields())


def test_v1_blocks_unresolved_citations_without_claiming_semantic_judgment():
    item = VerificationInput(
        question="Question",
        answer="Réponse",
        public_sources=["CNIL"],
        cited_evidence_ids=["MISSING"],
        claims=[],
        evidence=[{"evidence_id": "E1", "organization": "CNIL", "source_domain": "www.cnil.fr", "content": "Evidence"}],
    )
    result = verify_structure(item)
    assert result.verdict == "block"
    assert "MISSING" in result.citation_issues[0]
    assert "semantic support is not evaluated" in result.reasons[0]


def test_candidate_benchmark_has_claim_level_annotation_fields_and_resolvable_proposals():
    path = Path("benchmarks/response_verification_v1.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 30
    assert validate_rows(rows) == []
    human = [row for row in rows if row["annotation_status"] == "human_validated"]
    pending = [row for row in rows if row["annotation_status"] == "needs_human_validation"]
    assert len(human) == 24
    assert len(pending) == 6
    assert all(row["expected_verdict"] is not None for row in human)
    assert all(row["expected_public_source_correct"] is not None for row in human)
    assert all(row["expected_citation_resolution_correct"] is not None for row in human)
    assert all(claim["expected_support"] is not None for row in human for claim in row["claims"])
    assert all(row["expected_verdict"] is None for row in pending)
    assert all(row["expected_public_source_correct"] is None for row in pending)
    assert all(row["expected_citation_resolution_correct"] is None for row in pending)
    assert all(claim["expected_support"] is None for row in pending for claim in row["claims"])


def test_v2_request_transmits_the_verification_json_schema():
    item = VerificationInput(
        question="Question",
        answer="Réponse",
        public_sources=["CNIL"],
        cited_evidence_ids=["E1"],
        claims=[{"claim_id": "C1", "text": "Claim", "material": True}],
        evidence=[{"evidence_id": "E1", "organization": "CNIL", "source_domain": "www.cnil.fr", "content": "Evidence"}],
    )
    request = build_request(item)
    assert request.response_format is not None
    assert request.response_format["type"] == "json_schema"
    assert request.response_format["json_schema"]["name"] == "VerificationOutput"


def test_v3_cascade_preserves_v2_warning_and_blocks_on_v1_block():
    assert cascade_verdict("block", "pass") == "block"
    assert cascade_verdict("pass", "pass_with_warnings") == "pass_with_warnings"


def test_v3_replay_does_not_need_provider_or_benchmark_labels_for_predictions():
    raw = {
        "case_ids": ["VER-001", "VER-002"],
        "variants": {
            "V1": {"predictions": [
                {"case_id": "VER-001", "output": {"verdict": "block"}, "latency_ms": 1.0},
                {"case_id": "VER-002", "output": {"verdict": "pass"}, "latency_ms": 2.0},
            ]},
            "V2": {"predictions": [
                {"case_id": "VER-001", "output": {"verdict": "pass"}, "latency_ms": 10.0, "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}},
                {"case_id": "VER-002", "output": {"verdict": "pass_with_warnings"}, "latency_ms": 20.0, "usage": {"prompt_tokens": 20, "completion_tokens": 4, "total_tokens": 24}},
            ]},
        },
    }
    predictions = replay_predictions(raw)
    assert [item["output"]["verdict"] for item in predictions] == ["block", "pass_with_warnings"]
    assert predictions[0]["v2_call_used"] is False
    assert predictions[0]["usage"]["total_tokens"] == 0
    assert predictions[1]["v2_call_used"] is True
    assert predictions[1]["usage"]["total_tokens"] == 24


def test_v3_replay_metrics_use_same_verdict_definitions():
    rows = [
        {"id": "A", "expected_verdict": "block"},
        {"id": "B", "expected_verdict": "pass"},
        {"id": "C", "expected_verdict": "pass_with_warnings"},
    ]
    predictions = [
        {"case_id": "A", "output": {"verdict": "block"}, "latency_ms": 1, "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "v2_call_used": False},
        {"case_id": "B", "output": {"verdict": "pass"}, "latency_ms": 2, "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, "v2_call_used": True},
        {"case_id": "C", "output": {"verdict": "pass_with_warnings"}, "latency_ms": 3, "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, "v2_call_used": True},
    ]
    metrics = evaluate(rows, predictions)
    assert metrics["false_pass_rate"] == 0
    assert metrics["false_block_rate"] == 0
    assert metrics["v2_calls_avoided"] == 1
    assert metrics["claim_level_metrics"].startswith("NOT COMPARABLE")
