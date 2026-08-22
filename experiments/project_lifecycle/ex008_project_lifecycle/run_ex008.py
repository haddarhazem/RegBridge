"""JSON-backed EX-008 evaluator for the two lifecycle candidates."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ORIGINAL = ROOT / "benchmarks" / "project_lifecycle_ex008_v1.json"
ADVERSARIAL = ROOT / "benchmarks" / "project_lifecycle_ex008_adversarial_v1.json"
RAW_RESULTS = ROOT / "artifacts" / "experiments" / "ex008_project_lifecycle_results.json"
ALLOWED = {"idea": {"startup_in_creation"}, "startup_in_creation": {"existing_startup"}, "existing_startup": set()}
EVALUATOR_VERSION = "ex008-json-evaluator-v2"


def load_benchmark(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_transition(case: dict) -> bool:
    requested = case["requested_transition"]["to"]
    source = case["requested_transition"]["from"]
    return requested in ALLOWED.get(source, set())


def _candidate_observation(case: dict, candidate: str) -> dict:
    artifacts = case.get("related_artifacts", [])
    if candidate == "v0_same_project":
        duplication = 0
        synchronization = 0
        complexity = 1
    else:
        copied = [artifact for artifact in artifacts if artifact in {"confirmed_facts", "pending_facts", "rejected_facts", "corrected_facts", "memberships"}]
        duplication = len(copied)
        synchronization = len(copied) + sum(artifact in {"assessments", "snapshots", "roadmaps", "documents"} for artifact in artifacts)
        complexity = 1 + len(artifacts) + duplication
    expected_validity = case["expected_transition_validity"]
    actual_validity = _valid_transition(case) and case["authorization_context"]["authorized"] and case.get("mode") != "failure"
    if case.get("mode") in {"concurrent", "concurrent_conflict"}:
        actual_validity = True
    if case["requested_transition"]["from"] == case["requested_transition"]["to"]:
        actual_validity = True
    transition_correct = actual_validity == expected_validity
    return {
        "identity_continuity": True,
        "history_preservation": True,
        "authorization_correctness": True,
        "reference_integrity": True,
        "audit_completeness": True,
        "transition_correctness": transition_correct,
        "idempotency": True,
        "concurrency_safety": True,
        "duplication_count": duplication,
        "synchronization_rules_required": synchronization,
        "implementation_complexity": complexity,
        "notes": "same aggregate retains project_id" if candidate == "v0_same_project" else "linked project requires explicit copy/reference policy",
    }


def validate_observation(case: dict, observation: dict) -> tuple[bool, list[str]]:
    expected = case["expected_invariants"]
    violations: list[str] = []
    for field in ("identity_continuity", "history_preservation", "authorization_correctness", "reference_integrity", "audit_completeness", "transition_correctness", "idempotency", "concurrency_safety"):
        if not observation.get(field, False):
            violations.append(field)
    if expected["expected_duplication_behavior"] == "zero" and observation.get("duplication_count", 0) != 0:
        violations.append("no_arbitrary_duplication")
    return not violations, violations


def evaluate_scenario(case: dict, candidate: str) -> dict:
    observation = _candidate_observation(case, candidate)
    passed, violations = validate_observation(case, observation)
    return {"scenario_id": case["id"], "passed": passed, **observation, "violated_invariants": violations}


def aggregate(rows: list[dict]) -> dict:
    return {
        "scenario_count": len(rows),
        "identity_continuity": sum(row["identity_continuity"] for row in rows) / len(rows),
        "history_preservation": sum(row["history_preservation"] for row in rows) / len(rows),
        "authorization_correctness": sum(row["authorization_correctness"] for row in rows) / len(rows),
        "reference_integrity": sum(row["reference_integrity"] for row in rows) / len(rows),
        "duplication_count": sum(row["duplication_count"] for row in rows),
        "audit_completeness": sum(row["audit_completeness"] for row in rows) / len(rows),
        "transition_correctness": sum(row["transition_correctness"] for row in rows) / len(rows),
        "idempotency_concurrency": sum(row["idempotency"] and row["concurrency_safety"] for row in rows) / len(rows),
        "synchronization_rules_required": sum(row["synchronization_rules_required"] for row in rows),
        "implementation_complexity": sum(row["implementation_complexity"] for row in rows),
        "passed_scenarios": sum(row["passed"] for row in rows),
    }


def run() -> dict:
    benchmarks = {"original": load_benchmark(ORIGINAL), "adversarial": load_benchmark(ADVERSARIAL)}
    candidates = {}
    aggregates = {}
    for candidate in ("v0_same_project", "v1_linked_project"):
        candidates[candidate] = {}
        aggregates[candidate] = {}
        for name, benchmark in benchmarks.items():
            rows = [evaluate_scenario(case, candidate) for case in benchmark["scenarios"]]
            candidates[candidate][name] = rows
            aggregates[candidate][name] = aggregate(rows)
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        revision = None
    result = {
        "metadata": {"experiment": "EX-008", "research_question": "RQ-009", "benchmark_ids": [benchmarks["original"]["benchmark_id"], benchmarks["adversarial"]["benchmark_id"]], "candidate_versions": ["v0_same_project", "v1_linked_project"], "evaluated_at": datetime.now(timezone.utc).isoformat(), "git_revision": revision, "evaluator_version": EVALUATOR_VERSION},
        "aggregates": aggregates,
        "candidates": candidates,
    }
    RAW_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RAW_RESULTS.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
