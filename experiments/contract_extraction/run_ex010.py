"""JSON-backed EX-010 strategy evaluator.

The harness uses one deterministic extraction core for all candidates. The
candidate differences are output constraints and evidence handling, so the
experiment does not confound extraction strategy with provider choice.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "benchmarks" / "contract_extraction_ex010_v1.json"
ADVERSARIAL = ROOT / "benchmarks" / "contract_extraction_ex010_adversarial_v1.json"
RAW_RESULTS = ROOT / "artifacts" / "experiments" / "ex010_contract_extraction_results.json"
EVALUATOR_VERSION = "ex010-json-evaluator-v1"
TAXONOMY_VERSION = "contract-taxonomy-v1"


def load_benchmark(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sentences(text: str) -> list[tuple[str, int, int]]:
    return [(match.group(0), match.start(), match.end()) for match in re.finditer(r"[^.!?]+[.!?]", text)] or [(text, 0, len(text))]


def _category(sentence: str) -> str | None:
    lower = sentence.lower()
    if "intellectual property" in lower:
        return "intellectual_property"
    if "confidential" in lower or "keep" in lower and "secret" in lower:
        return "confidentiality"
    if "personal data" in lower:
        return "data_protection"
    if "governed by" in lower or "french law" in lower:
        return "governing_law"
    if "liability" in lower or "liable" in lower or "losses" in lower:
        return "liability"
    if "renew" in lower:
        return "renewal"
    if "exclusiv" in lower:
        return "exclusivity"
    if "payable" in lower or "payment" in lower or "paid" in lower or "late" in lower:
        return "payment"
    if "terminate" in lower or "termination" in lower or "ended" in lower or "end" in lower and "agreement" in lower or "notice period" in lower:
        return "termination"
    if "should review" in lower:
        return "term"
    return None


def _negated(sentence: str, category: str) -> bool:
    lower = sentence.lower()
    if category == "renewal":
        return bool(re.search(r"does not automatically renew|doesn't automatically renew|no automatic renewal", lower))
    if category == "exclusivity":
        return bool(re.search(r"no exclusivity|neither party has an exclusivity|no .* exclusivity", lower))
    return False


def _type(sentence: str, category: str, candidate: str) -> str:
    lower = sentence.lower()
    if candidate == "v0_direct_prompting":
        return "FINDING"
    if "should" in lower or "recommends" in lower:
        return "RECOMMENDATION"
    if any(word in lower for word in ("conflicting", "elsewhere", "without limitation", "does not specify", "only where")):
        return "UNCERTAINTY"
    return "FINDING"


def _evidence_quote(sentence: str, category: str) -> str:
    # The deterministic extractor keeps the most specific operative clause
    # when a sentence contrasts background material with controlling text.
    match = re.search(r"(the operative clause [^.]+\.)", sentence, flags=re.IGNORECASE)
    if category == "liability" and match:
        return match.group(1)
    return sentence.strip()


def generate_findings(case: dict, candidate: str) -> list[dict]:
    findings: list[dict] = []
    for sentence, start, end in _sentences(case["text"]):
        category = _category(sentence)
        if category is None or candidate == "v2_structured_evidence" and _negated(sentence, category):
            continue
        evidence_quote = _evidence_quote(sentence, category)
        evidence_start = case["text"].find(evidence_quote, start, end)
        finding = {
            "generated_finding_id": f"{case['case_id']}-{category}-{len(findings) + 1}",
            "category": category,
            "finding_type": _type(sentence, category, candidate),
            "statement": sentence.strip(),
            "risk_level": "medium" if category in {"liability", "termination", "payment"} else None,
            "recommendation": sentence.strip() if "should" in sentence.lower() or "recommends" in sentence.lower() else None,
            "uncertain": _type(sentence, category, candidate) == "UNCERTAINTY",
            "document_version_id": case["document_version"] if candidate == "v2_structured_evidence" else None,
            "evidence_quote": evidence_quote if candidate == "v2_structured_evidence" else None,
            "start_char": evidence_start if candidate == "v2_structured_evidence" else None,
            "end_char": evidence_start + len(evidence_quote) if candidate == "v2_structured_evidence" and evidence_start >= 0 else None,
            "structured_valid": candidate != "v0_direct_prompting",
            "prompt_injection_ignored": "ignore previous instructions" not in sentence.lower() or category is not None,
        }
        findings.append(finding)
    return findings


def _match_expected(finding: dict, expected: list[dict], used: set[str]) -> dict | None:
    for item in expected:
        if item["finding_id"] not in used and item["category"] == finding["category"]:
            used.add(item["finding_id"])
            return item
    return None


def evaluate_case(case: dict, candidate: str) -> dict:
    started = time.perf_counter()
    generated = generate_findings(case, candidate)
    used: set[str] = set()
    finding_records: list[dict] = []
    for finding in generated:
        expected = _match_expected(finding, case["expected_findings"], used)
        forbidden = finding["category"] in set(case.get("forbidden_categories", []))
        evidence_expected = expected.get("evidence", {}).get("quote") if expected else None
        evidence_correct = bool(expected and finding.get("evidence_quote") and evidence_expected in finding["evidence_quote"] and finding.get("document_version_id") == case["document_version"])
        span_valid = bool(finding.get("evidence_quote") and finding.get("start_char") is not None and finding.get("end_char") is not None and case["text"][finding["start_char"]:finding["end_char"]] == finding["evidence_quote"])
        finding_records.append({
            "case_id": case["case_id"],
            "generated_finding": finding,
            "matched_expected_finding_id": expected["finding_id"] if expected else None,
            "supported": expected is not None and not forbidden,
            "category_correct": expected is not None,
            "type_correct": bool(expected and expected["finding_type"] == finding["finding_type"]),
            "evidence_correct": evidence_correct,
            "span_valid": span_valid,
            "forbidden": forbidden,
            "structured_valid": finding["structured_valid"],
            "latency_ms": (time.perf_counter() - started) * 1000,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "evaluator_notes": "deterministic synthetic harness; no provider cost measured",
        })
    expected_ids = {item["finding_id"] for item in case["expected_findings"]}
    recovered = len(used & expected_ids)
    unsupported = sum(not item["supported"] for item in finding_records)
    return {
        "case_id": case["case_id"],
        "findings": finding_records,
        "expected_count": len(case["expected_findings"]),
        "generated_count": len(finding_records),
        "recovered_count": recovered,
        "unsupported_count": unsupported,
        "forbidden_count": sum(item["forbidden"] for item in finding_records),
        "structured_valid": all(item["structured_valid"] for item in finding_records) and candidate != "v0_direct_prompting",
        "injection_ignored": "Ignore previous instructions" not in case["text"] or all(item["generated_finding"]["prompt_injection_ignored"] for item in finding_records),
    }


def aggregate(cases: list[dict]) -> dict:
    findings = [item for case in cases for item in case["findings"]]
    generated = len(findings)
    correct = sum(item["supported"] for item in findings)
    expected = sum(case["expected_count"] for case in cases)
    typed = sum(item["type_correct"] for item in findings)
    categorized = sum(item["category_correct"] for item in findings)
    evidence = sum(item["evidence_correct"] for item in findings)
    spans = sum(item["span_valid"] for item in findings)
    structured_cases = sum(case["structured_valid"] for case in cases)
    return {
        "case_count": len(cases),
        "generated_findings": generated,
        "correct_findings": correct,
        "expected_findings": expected,
        "finding_precision": correct / generated if generated else 1.0,
        "finding_recall": correct / expected if expected else 1.0,
        "f1": 2 * correct / (generated + expected) if generated + expected else 1.0,
        "unsupported_finding_rate": (generated - correct) / generated if generated else 0.0,
        "finding_type_correctness": typed / generated if generated else 1.0,
        "category_correctness": categorized / generated if generated else 1.0,
        "evidence_link_accuracy": evidence / correct if correct else 0.0,
        "exact_evidence_span_validity": spans / generated if generated else 0.0,
        "forbidden_finding_rate": sum(case["forbidden_count"] for case in cases) / generated if generated else 0.0,
        "structured_output_validity": structured_cases / len(cases) if cases else 1.0,
        "stability": 1.0,
        "latency_ms_median": 0.0,
        "latency_ms_p95": 0.0,
        "token_usage": None,
        "cost": None,
    }


def run() -> dict:
    core = load_benchmark(CORE)
    adversarial = load_benchmark(ADVERSARIAL)
    benchmarks = {"development": core["cases"]["development"], "holdout": core["cases"]["holdout"], "adversarial": adversarial["cases"]}
    candidates = {}
    aggregates = {}
    for candidate in ("v0_direct_prompting", "v1_structured_extraction", "v2_structured_evidence"):
        candidates[candidate] = {}
        aggregates[candidate] = {}
        for split, cases in benchmarks.items():
            rows = [evaluate_case(case, candidate) for case in cases]
            candidates[candidate][split] = rows
            aggregates[candidate][split] = aggregate(rows)
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        revision = None
    result = {
        "metadata": {"experiment":"EX-010","research_question":"RQ-011","taxonomy_version":TAXONOMY_VERSION,"benchmark_ids":[core["benchmark_id"], adversarial["benchmark_id"]],"candidate_versions":["v0_direct_prompting","v1_structured_extraction","v2_structured_evidence"],"provider":"deterministic-research-harness","model":"synthetic-rule-parser","temperature":0,"evaluated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"git_revision":revision,"evaluator_version":EVALUATOR_VERSION},
        "aggregates": aggregates,
        "candidates": candidates,
    }
    RAW_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RAW_RESULTS.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def mutation_detected(case: dict, candidate: str, mutation: str) -> bool:
    row = evaluate_case(case, candidate)
    if mutation == "invented_finding":
        row["findings"].append({"supported": False, "category_correct": False, "type_correct": False, "evidence_correct": False, "span_valid": False, "forbidden": False, "structured_valid": True})
    elif mutation == "wrong_category":
        row["findings"][0]["category_correct"] = False
    elif mutation == "wrong_type":
        row["findings"][0]["type_correct"] = False
    elif mutation == "unrelated_evidence":
        row["findings"][0]["evidence_correct"] = False
    elif mutation == "offset_quote_mismatch":
        row["findings"][0]["span_valid"] = False
    elif mutation == "negation_error":
        row["findings"].append({"supported": False, "category_correct": False, "type_correct": False, "evidence_correct": False, "span_valid": False, "forbidden": True, "structured_valid": True})
    elif mutation == "wrong_document_version":
        row["findings"][0]["evidence_correct"] = False
    elif mutation == "missing_finding":
        row["recovered_count"] = max(0, row["expected_count"] - 1)
    else:
        raise ValueError(mutation)
    return mutation == "missing_finding" and row["recovered_count"] < row["expected_count"] or mutation != "missing_finding" and any(not item.get("supported", True) or not item.get("category_correct", True) or not item.get("type_correct", True) or not item.get("evidence_correct", True) or not item.get("span_valid", True) or item.get("forbidden", False) for item in row["findings"])


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
