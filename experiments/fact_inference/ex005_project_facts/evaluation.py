from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from .contracts import ExtractedFact


def evaluate(cases: list[dict[str, Any]], outputs: dict[str, list[ExtractedFact]], metadata: dict[str, dict[str, Any]]) -> dict[str, Any]:
    expected_total = sum(len(case["expected_facts"]) for case in cases)
    inferred = [fact for case in cases for fact in outputs.get(case["id"], [])]
    expected = {(case["id"], item["domain"], item["value"]): item for case in cases for item in case["expected_facts"]}
    correct = sum((case["id"], fact.domain, fact.value) in expected for case in cases for fact in outputs.get(case["id"], []))
    recalled = sum(1 for case in cases for item in case["expected_facts"] if (case["id"], item["domain"], item["value"]) in {(case["id"], fact.domain, fact.value) for fact in outputs.get(case["id"], [])})
    unsupported = len(inferred) - correct
    with_provenance = sum(bool(fact.provenance.excerpt) for fact in inferred)
    provenance_correct = sum(
        fact.provenance.excerpt.lower() in case["description"].lower()
        for case in cases for fact in outputs.get(case["id"], [])
    )
    ambiguous_cases = [(case["id"], item) for case in cases for item in case["expected_facts"] if item.get("ambiguous")]
    unresolved = sum(
        any(f.domain == item["domain"] and (f.uncertainty != "high" or f.value in {"à préciser", "à définir", "inconnu"}) for f in outputs.get(case_id, []))
        for case_id, item in ambiguous_cases
    )
    valid_attempts = sum(bool(metadata.get(case["id"], {}).get("valid")) for case in cases)
    attempts = len(cases)
    latencies = [float(metadata[case["id"]]["latency_ms"]) for case in cases if metadata.get(case["id"], {}).get("latency_ms") is not None]
    return {
        "cases": len(cases), "expected_facts": expected_total, "inferred_facts": len(inferred),
        "correct_facts": correct, "precision": correct / len(inferred) if inferred else 1.0,
        "recall": recalled / expected_total if expected_total else 1.0,
        "f1": (2 * correct / (len(inferred) + expected_total)) if len(inferred) + expected_total else 1.0,
        "unsupported_inference_rate": unsupported / len(inferred) if inferred else 0.0,
        "provenance_correctness": provenance_correct / with_provenance if with_provenance else 1.0,
        "ambiguity_preservation": unresolved / len(ambiguous_cases) if ambiguous_cases else 1.0,
        "structured_output_validity": valid_attempts / attempts if attempts else 1.0,
        "latency_median_ms": median(latencies) if latencies else None,
        "latency_p95_ms": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] if latencies else None,
        "token_usage": {key: sum(float(metadata.get(case["id"], {}).get("usage", {}).get(key, 0) or 0) for case in cases) for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
    }
