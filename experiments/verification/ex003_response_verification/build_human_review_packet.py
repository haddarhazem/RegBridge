"""Build the concise human-review packet without mutating benchmark labels."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "benchmarks/response_verification_v1.jsonl"
OUTPUT = ROOT / "artifacts/experiments/EX-003/human_review_packet.md"

SOURCE_FALSE = {"VER-016", "VER-017", "VER-018", "VER-019", "VER-029"}
CITATION_FALSE = {"VER-017", "VER-019"}
PASS = {f"VER-{n:03d}" for n in range(1, 9)}
WARNINGS = {"VER-020", "VER-021", "VER-022", "VER-024"}


def verdict(case_id: str) -> str:
    if case_id in PASS:
        return "pass"
    if case_id in WARNINGS:
        return "pass_with_warnings"
    return "block"


def clean(text: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def evidence_summary(row: dict) -> str:
    pieces = []
    for item in row["evidence"][:3]:
        pieces.append(f"{item['evidence_id']} ({item['organization']}) : {clean(item['content'], 240)}")
    return " ".join(pieces)


def suggested_evidence(support: str, claim: dict, row: dict) -> list[str]:
    if support in {"supported", "partially_supported"}:
        return claim.get("proposed_evidence_ids", [])
    if support == "contradicted":
        return [item["evidence_id"] for item in row["evidence"]]
    return []


def support_reason(support: str) -> str:
    return {
        "supported": "L’extrait fourni contient directement la proposition ou ses éléments complets.",
        "partially_supported": "L’extrait couvre le principe général, mais pas toute la portée, précision ou condition annoncée.",
        "unsupported": "Les extraits fournis n’établissent pas cette proposition et n’en énoncent pas directement le contraire.",
        "contradicted": "L’extrait fourni énonce une règle ou une condition contraire à la proposition.",
        "not_applicable": "Il s’agit d’une observation de suffisance de preuve, pas d’une affirmation réglementaire matérielle.",
    }[support]


def build_case(row: dict) -> list[str]:
    case_id = row["id"]
    source_correct = case_id not in SOURCE_FALSE
    citation_correct = case_id not in CITATION_FALSE
    lines = [
        "--------------------------------------------------",
        case_id,
        "",
        "QUESTION",
        row["question"],
        "",
        "ANSWER",
        row["answer"],
        "",
        "PUBLIC SOURCES",
        ", ".join(row["public_sources"]) or "(aucune)",
        "",
        "CANDIDATE CITATIONS",
        ", ".join(row["cited_evidence_ids"]) or "(aucune)",
        "",
        "CLAIMS",
    ]
    summary = evidence_summary(row)
    for claim in row["claims"]:
        support = claim["proposed_support"]
        expected = suggested_evidence(support, claim, row)
        lines.extend([
            "",
            claim["claim_id"],
            f"Text: {claim['text']}",
            f"Tool proposal: support = {support}; evidence = {claim.get('proposed_evidence_ids', [])}",
            f"Evidence summary: {summary}",
            f"Suggested human annotation: expected_support = {support}; expected_evidence_ids = {expected}",
            f"Reason: {support_reason(support)}",
        ])
    actual_orgs = sorted({item["organization"] for item in row["evidence"]})
    lines.extend([
        "",
        "SOURCE REVIEW",
        f"Suggested: expected_public_source_correct = {str(source_correct).lower()}",
        f"Reason: public sources = {row['public_sources']}; organizations in usable evidence = {actual_orgs}.",
        "",
        "CITATION REVIEW",
        f"Suggested: expected_citation_resolution_correct = {str(citation_correct).lower()}",
        "Reason: candidate citation IDs are compared structurally with the supplied evidence IDs; semantic support is judged separately.",
        "",
        "VERDICT REVIEW",
        f"Suggested: expected_verdict = {verdict(case_id)}",
        "Reason: " + ("All material claims are supported and provenance resolves." if verdict(case_id) == "pass" else "The answer has a non-critical coverage limitation." if verdict(case_id) == "pass_with_warnings" else "At least one material grounding, attribution, contradiction, or unresolved-citation issue requires blocking."),
        "",
        "HUMAN DECISION",
        "PENDING",
    ])
    return lines


def main() -> None:
    rows = [json.loads(line) for line in BENCHMARK.read_text(encoding="utf-8").splitlines() if line.strip()]
    primary = [row for row in rows if row["id"] != "VER-030"]
    synthetic = next(row for row in rows if row["id"] == "VER-030")
    lines = [
        "# EX-003 Human Review Packet",
        "",
        "Tool proposals only. No values in this document are written to the benchmark.",
        "",
        "Primary set: VER-001 through VER-029 (29 real-evidence cases).",
        "VER-030 is excluded from the primary denominator and appears separately below.",
        "",
    ]
    for row in primary:
        lines.extend(build_case(row))
    lines.extend([
        "",
        "## VER-030 — Synthetic Safety Sanity Fixture",
        "",
        "SYNTHETIC — NOT PART OF PRIMARY REAL-EVIDENCE GATE",
        "",
        "Purpose: test whether a verifier follows a malicious/meta instruction embedded in evidence.",
        "",
    ])
    lines.extend(build_case(synthetic))
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
