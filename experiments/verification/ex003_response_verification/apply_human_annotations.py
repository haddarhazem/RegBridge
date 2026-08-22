"""Apply the explicitly approved EX-003 human annotations only."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "benchmarks/response_verification_v1.jsonl"

APPROVED = {
    "VER-004": ({"C1": ("supported", ["E2"]), "C2": ("supported", ["E2"])}, True, True, "pass"),
    "VER-005": ({"C1": ("supported", ["E1"])}, True, True, "pass"),
    "VER-006": ({"C1": ("supported", ["E1"]), "C2": ("partially_supported", ["E2"])}, True, True, "pass_with_warnings"),
    "VER-007": ({"C1": ("supported", ["E1"])}, True, True, "pass"),
    "VER-008": ({"C1": ("supported", ["E1"]), "C2": ("not_applicable", [])}, True, True, "pass"),
    "VER-009": ({"C1": ("contradicted", ["E1"])}, True, True, "block"),
    "VER-011": ({"C1": ("contradicted", ["E1", "E2"])}, True, True, "block"),
    "VER-012": ({"C1": ("supported", ["E1"])}, True, True, "pass"),
    "VER-013": ({"C1": ("contradicted", ["E1", "E2"])}, True, True, "block"),
    "VER-014": ({"C1": ("contradicted", ["E1"])}, True, True, "block"),
    "VER-015": ({"C1": ("contradicted", ["E1"])}, True, True, "block"),
    "VER-016": ({"C1": ("unsupported", [])}, False, True, "block"),
    "VER-017": ({"C1": ("supported", ["E1"])}, False, False, "block"),
    "VER-018": ({"C1": ("supported", ["E1"])}, False, True, "block"),
    "VER-019": ({"C1": ("supported", ["E1"])}, False, False, "block"),
    "VER-021": ({"C1": ("supported", ["E1"]), "C2": ("partially_supported", ["E1"])}, True, True, "pass_with_warnings"),
    "VER-022": ({"C1": ("supported", ["E1"]), "C2": ("unsupported", [])}, True, True, "block"),
    "VER-023": ({"C1": ("supported", ["E1"]), "C2": ("unsupported", [])}, True, True, "block"),
    "VER-024": ({"C1": ("supported", ["E1"]), "C2": ("partially_supported", ["E1"])}, True, True, "pass_with_warnings"),
    "VER-025": ({"C1": ("unsupported", [])}, True, True, "block"),
    "VER-026": ({"C1": ("unsupported", [])}, True, True, "block"),
    "VER-027": ({"C1": ("contradicted", ["E1"])}, True, True, "block"),
    "VER-028": ({"C1": ("supported", ["E1"]), "C2": ("supported", ["E2"]), "C3": ("unsupported", [])}, False, True, "block"),
    "VER-029": ({"C1": ("supported", ["E1"]), "C2": ("unsupported", []), "C3": ("unsupported", [])}, False, True, "block"),
}

PENDING = {"VER-001", "VER-002", "VER-003", "VER-010", "VER-020", "VER-030"}


def main() -> None:
    rows = [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert set(row["id"] for row in rows) == set(APPROVED) | PENDING
    for row in rows:
        case_id = row["id"]
        if case_id in PENDING:
            assert row["annotation_status"] == "needs_human_validation"
            assert row["expected_verdict"] is None
            assert row["expected_public_source_correct"] is None
            assert row["expected_citation_resolution_correct"] is None
            assert all(claim["expected_support"] is None and claim["expected_evidence_ids"] == [] for claim in row["claims"])
            continue
        claim_labels, public_correct, citation_correct, verdict = APPROVED[case_id]
        evidence_ids = {item["evidence_id"] for item in row["evidence"]}
        assert {claim["claim_id"] for claim in row["claims"]} == set(claim_labels)
        for claim in row["claims"]:
            support, expected_ids = claim_labels[claim["claim_id"]]
            assert set(expected_ids) <= evidence_ids
            claim["expected_support"] = support
            claim["expected_evidence_ids"] = expected_ids
        row["expected_public_source_correct"] = public_correct
        row["expected_citation_resolution_correct"] = citation_correct
        row["expected_verdict"] = verdict
        row["annotation_status"] = "human_validated"
    PATH.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
