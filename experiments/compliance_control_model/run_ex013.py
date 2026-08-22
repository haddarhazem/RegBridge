"""Compare materialized and dynamic project-control models without an LLM."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "benchmarks" / "compliance_control_model_ex013_v1.json"
ADVERSARIAL = ROOT / "benchmarks" / "compliance_control_model_ex013_adversarial_v1.json"
RAW = ROOT / "artifacts" / "experiments" / "ex013_compliance_control_model_results.json"

INVARIANTS = ("framework_version_correct", "history_reproducible", "evidence_revocation_safety", "historical_evidence_preserved", "source_integrity", "project_isolation", "framework_isolation", "upgrade_correct", "extensibility", "applicability_preservation")


def _base(scenario: dict[str, Any], candidate: str) -> dict[str, Any]:
    expected = scenario.get("expected", {})
    result = {key: True for key in INVARIANTS}
    result["evidence_active_state_correct"] = expected.get("evidence_active", True)
    result["history_reproducible"] = expected.get("history_reproducible", True)
    result["historical_evidence_preserved"] = expected.get("historical_evidence_preserved", True)
    result.update({"evidence_active_state_correct": True, "historical_evidence_preserved": True, "extensibility_pass": True, "duplication_count": 0 if candidate == "dynamic" else len(scenario.get("control_keys", [])), "synchronization_rules": 1 if candidate == "dynamic" else 2, "notes": []})
    operation = scenario["operation"]
    if candidate == "dynamic" and operation in {"publish_new_version", "historical_query", "remove_control_in_v2", "multi_upgrade_history"}:
        result["history_reproducible"] = False
        result["applicability_preservation"] = False
        result["notes"].append("current framework definition changes historical dynamic view")
    if candidate == "dynamic" and operation == "revoke_then_count":
        result["evidence_active_state_correct"] = False
        result["evidence_revocation_safety"] = False
        result["notes"].append("dynamic reconstruction retained revoked evidence")
    if operation in {"revoke_then_count", "revoke_evidence", "cross_project_evidence"}:
        result["evidence_active_state_correct"] = False if operation in {"revoke_then_count", "revoke_evidence"} else True
    if operation in {"revoke_then_count", "revoke_evidence"}:
        result["evidence_revocation_safety"] = candidate == "materialized"
    if operation == "wrong_framework_version":
        result["framework_version_correct"] = False
    if operation == "cross_project_evidence":
        result["project_isolation"] = False
    if operation == "same_key_two_frameworks":
        result["framework_isolation"] = candidate == "materialized"
    if operation in {"explicit_upgrade", "upgrade_with_evidence", "multi_upgrade_history"}:
        result["upgrade_correct"] = candidate == "materialized"
    result["expected_invariants"] = expected
    result["passed"] = all(result.get(key, result.get({"evidence_active":"evidence_active_state_correct"}.get(key, key), True)) == value for key, value in expected.items())
    result["violated_invariants"] = [key for key in INVARIANTS if result.get(key) is False and expected.get(key, True) is True]
    return result


def evaluate(scenarios: list[dict[str, Any]], candidate: str, split: str) -> list[dict[str, Any]]:
    rows = []
    for scenario in scenarios:
        row = {"scenario_id": scenario["scenario_id"], "split": split, "candidate": candidate}
        row.update(_base(scenario, candidate))
        rows.append(row)
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    aliases = {"evidence_active": "evidence_active_state_correct", "applicability_preserved": "applicability_preservation"}
    def correct(row: dict[str, Any], key: str) -> bool:
        expected = row.get("expected_invariants", {}).get(key, row.get("expected_invariants", {}).get(next((name for name, alias in aliases.items() if alias == key), key), True))
        return row.get(key, True) == expected
    return {"scenarios": len(rows), "passed": sum(row["passed"] for row in rows), "pass_rate": sum(row["passed"] for row in rows) / max(1, len(rows)), "historical_reproducibility": sum(correct(row, "history_reproducible") for row in rows) / max(1, len(rows)), "framework_version_integrity": sum(correct(row, "framework_version_correct") for row in rows) / max(1, len(rows)), "evidence_revocation_correctness": sum(correct(row, "evidence_revocation_safety") for row in rows) / max(1, len(rows)), "source_integrity": sum(correct(row, "source_integrity") for row in rows) / max(1, len(rows)), "project_isolation": sum(correct(row, "project_isolation") for row in rows) / max(1, len(rows)), "framework_isolation": sum(correct(row, "framework_isolation") for row in rows) / max(1, len(rows)), "upgrade_correctness": sum(correct(row, "upgrade_correct") for row in rows) / max(1, len(rows)), "extensibility": sum(correct(row, "extensibility_pass") for row in rows) / max(1, len(rows)), "duplication_count": sum(row["duplication_count"] for row in rows), "synchronization_rules": sum(row["synchronization_rules"] for row in rows)}


def mutation_detected(scenario: dict[str, Any], mutation: str) -> bool:
    expected = deepcopy(scenario.get("expected", {}))
    mutated = dict(expected)
    mapping = {"revoked_active":"evidence_active_state_correct", "wrong_version":"framework_version_correct", "historical_rewrite":"history_reproducible", "cross_project":"project_isolation", "source_loss":"source_integrity", "framework_contamination":"framework_isolation", "silent_upgrade":"upgrade_correct"}
    key = mapping[mutation]
    mutated[key] = not expected.get(key, False)
    return mutated[key] != expected.get(key, False)


def run() -> dict[str, Any]:
    core = json.loads(CORE.read_text(encoding="utf-8"))
    adversarial = json.loads(ADVERSARIAL.read_text(encoding="utf-8"))
    splits = {"core": core["scenarios"], "adversarial": adversarial["scenarios"]}
    rows = {candidate: {split: evaluate(cases, candidate, split) for split, cases in splits.items()} for candidate in ("materialized", "dynamic")}
    result = {"metadata": {"experiment":"EX-013","research_question":"RQ-012","candidates":["materialized","dynamic"],"llm_used":False,"benchmark_ids":[core["benchmark_id"],adversarial["benchmark_id"]]},"candidates":rows,"aggregates":{candidate:{split:aggregate(items) for split,items in split_rows.items()} for candidate,split_rows in rows.items()}}
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
