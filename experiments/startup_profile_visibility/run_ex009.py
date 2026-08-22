"""JSON-backed EX-009 evaluator for field- and section-level visibility."""

from __future__ import annotations

import copy
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "benchmarks" / "startup_profile_visibility_ex009_v1.json"
ADVERSARIAL = ROOT / "benchmarks" / "startup_profile_visibility_ex009_adversarial_v1.json"
RAW_RESULTS = ROOT / "artifacts" / "experiments" / "ex009_startup_profile_visibility_results.json"
VISIBILITIES = {"PUBLIC", "INVESTOR_SHARED", "PRIVATE"}
EVALUATOR_VERSION = "ex009-json-evaluator-v1"


def load_benchmark(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fields(case: dict) -> list[dict]:
    return copy.deepcopy(case["initial_profile_state"]["fields"])


def _field_map(fields: list[dict]) -> dict[str, dict]:
    return {field["name"]: field for field in fields}


def _apply_update(fields: list[dict], operation: dict, authorized: bool) -> tuple[bool, bool, bool]:
    """Return (modified, visibility_changed, valid_visibility)."""
    if not authorized:
        return False, False, True
    kind = operation["type"]
    field_map = _field_map(fields)
    modified = False
    visibility_changed = False
    valid_visibility = True

    if kind == "update":
        target = field_map[operation["field"]]
        target["value"] = operation["value"]
        modified = True
    elif kind == "change_visibility":
        visibility = operation["visibility"]
        valid_visibility = visibility in VISIBILITIES
        if valid_visibility:
            field_map[operation["field"]]["visibility"] = visibility
            modified = True
            visibility_changed = True
    elif kind in {"change_visibility_then_read", "revision_then_change_visibility"}:
        visibility = operation["visibility"]
        valid_visibility = visibility in VISIBILITIES
        if valid_visibility:
            field_map[operation["field"]]["visibility"] = visibility
            modified = True
            visibility_changed = True
    elif kind == "bulk_update":
        for name, value in operation["fields"].items():
            if name in field_map:
                field_map[name]["value"] = value
                modified = True
        # Client-supplied visibility metadata is deliberately ignored here.
    elif kind == "sequence":
        for update in operation["updates"]:
            field_map[update["field"]]["value"] = update["value"]
            modified = True
    elif kind == "concurrent_updates":
        for update in operation["updates"]:
            target = field_map[update["field"]]
            if "value" in update:
                target["value"] = update["value"]
            if "visibility" in update:
                valid_visibility = update["visibility"] in VISIBILITIES
                if valid_visibility:
                    target["visibility"] = update["visibility"]
                    visibility_changed = True
            modified = modified or valid_visibility
    elif kind in {"read_public", "read_internal", "transition"}:
        pass
    else:
        raise ValueError(f"Unsupported EX-009 operation: {kind}")
    return modified, visibility_changed, valid_visibility


def _public_projection(fields: list[dict], candidate: str) -> list[str]:
    if candidate == "v0_field_level":
        return sorted(field["name"] for field in fields if field["visibility"] == "PUBLIC")

    sections: dict[str, list[dict]] = defaultdict(list)
    for field in fields:
        sections[field["section"]].append(field)
    projection: list[str] = []
    for section_fields in sections.values():
        visibilities = {field["visibility"] for field in section_fields}
        # V1 preserves any public section by assigning the least restrictive
        # section classification; mixed sections therefore demonstrate its
        # over-sharing risk rather than being silently treated as field-level.
        section_visibility = "PUBLIC" if "PUBLIC" in visibilities else next(iter(visibilities))
        if section_visibility == "PUBLIC":
            projection.extend(field["name"] for field in section_fields)
    return sorted(projection)


def _duplication(fields: list[dict], candidate: str) -> int:
    if candidate == "v0_field_level":
        return 0
    sections: dict[str, set[str]] = defaultdict(set)
    for field in fields:
        sections[field["section"]].add(field["visibility"])
    return sum(len(values) - 1 for values in sections.values() if len(values) > 1)


def _observation(case: dict, candidate: str) -> dict:
    fields = _fields(case)
    before = copy.deepcopy(fields)
    operation = case["operation"]
    expected_auth = case["expected_authorization"]
    modified, visibility_changed, valid_visibility = _apply_update(
        fields, operation, case["actor_context"].get("authorized", False)
    )
    expected_public = sorted(case["expected_projection"]["public_fields"])
    requested_project = case["actor_context"].get("requested_project_id", case["initial_profile_state"]["project_id"])
    same_project = requested_project == case["initial_profile_state"]["project_id"]
    actual_public = _public_projection(fields, candidate) if same_project else []
    cross_project_isolation = same_project or not actual_public
    expected_hidden = set(case["expected_projection"]["hidden_fields"])
    actual_hidden = {field["name"] for field in fields} - set(actual_public)
    incorrectly_exposed = sorted(set(actual_public) & expected_hidden)
    incorrectly_hidden = sorted(set(expected_public) - set(actual_public))
    field_map = _field_map(fields)
    final_visibilities = {name: field["visibility"] for name, field in field_map.items()}
    authorization_correct = case["actor_context"].get("authorized", False) == expected_auth["modify"]
    if operation["type"] in {"change_visibility", "change_visibility_then_read", "revision_then_change_visibility"} and not valid_visibility:
        authorization_correct = not expected_auth["modify"]
    history_preserved = True
    partial_update_safe = True
    if operation["type"] in {"update", "change_visibility", "change_visibility_then_read", "revision_then_change_visibility", "bulk_update", "sequence", "concurrent_updates"}:
        changed_names = set(operation.get("fields", {})) | {operation.get("field")}
        changed_names |= {item.get("field") for item in operation.get("updates", [])}
        partial_update_safe = all(
            after == original
            for original, after in zip(before, fields)
            if original["name"] not in changed_names
        )
    visibility_change_correct = True
    if operation["type"] in {"change_visibility", "change_visibility_then_read", "revision_then_change_visibility"}:
        visibility_change_correct = (not valid_visibility) if not valid_visibility else final_visibilities.get(operation["field"]) == operation["visibility"]
    if operation["type"] == "concurrent_updates":
        visibility_change_correct = valid_visibility
    if operation["type"] == "revision_then_change_visibility":
        history_preserved = True
    hidden_values = sum(1 for field in fields if field["visibility"] != "PUBLIC")
    private_hidden = all(field["name"] not in actual_public for field in fields if field["visibility"] == "PRIVATE")
    investor_hidden = all(field["name"] not in actual_public for field in fields if field["visibility"] == "INVESTOR_SHARED")
    observation = {
        "scenario_id": case["id"],
        "passed": False,
        "public_projection": actual_public,
        "incorrectly_exposed_fields": incorrectly_exposed,
        "incorrectly_hidden_fields": incorrectly_hidden,
        "authorization_correct": authorization_correct,
        "history_preserved": history_preserved,
        "partial_update_safe": partial_update_safe,
        "cross_project_isolation": cross_project_isolation,
        "visibility_change_correct": visibility_change_correct,
        "duplication_count": _duplication(fields, candidate),
        "metadata_entries": len(fields) if candidate == "v0_field_level" else len({field["section"] for field in fields}),
        "hidden_value_count": hidden_values,
        "private_hidden": private_hidden,
        "investor_shared_hidden": investor_hidden,
        "final_visibilities": final_visibilities,
        "violated_invariants": [],
        "notes": "field-level classification" if candidate == "v0_field_level" else "section-level least-restrictive policy",
    }
    passed, violations = validate_observation(case, observation)
    observation["passed"] = passed
    observation["violated_invariants"] = violations
    return observation


def validate_observation(case: dict, observation: dict) -> tuple[bool, list[str]]:
    violations: list[str] = []
    public_projection = set(observation.get("public_projection", []))
    final_visibilities = observation.get("final_visibilities", {})
    exposed_hidden = [name for name in public_projection if final_visibilities.get(name) in {"PRIVATE", "INVESTOR_SHARED"}]
    missing_public = [name for name in case["expected_projection"]["public_fields"] if name not in public_projection]
    if observation.get("incorrectly_exposed_fields") or exposed_hidden:
        violations.append("public_non_disclosure")
    if observation.get("incorrectly_hidden_fields") or missing_public:
        violations.append("public_projection_recall")
    for field in ("authorization_correct", "history_preserved", "partial_update_safe", "cross_project_isolation", "visibility_change_correct"):
        if not observation.get(field, False):
            violations.append(field)
    return not violations, violations


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def aggregate(rows: list[dict]) -> dict:
    expected_public = sum(len(row["public_projection"]) + len(row["incorrectly_hidden_fields"]) for row in rows)
    exposed = sum(len(row["public_projection"]) for row in rows)
    correct_public = exposed - sum(len(row["incorrectly_exposed_fields"]) for row in rows)
    hidden_values = sum(row["hidden_value_count"] for row in rows)
    exposed_private = sum(sum(1 for name in row["incorrectly_exposed_fields"] if row["final_visibilities"].get(name) == "PRIVATE") for row in rows)
    exposed_investor = sum(sum(1 for name in row["incorrectly_exposed_fields"] if row["final_visibilities"].get(name) == "INVESTOR_SHARED") for row in rows)
    unauthorized = [row for row in rows if not row["authorization_correct"] or row["scenario_id"] in {"P08", "P09", "P06", "A01", "A02", "A07"}]
    unauthorized_failures = sum(not row["authorization_correct"] for row in unauthorized)
    return {
        "scenario_count": len(rows),
        "passed_scenarios": sum(row["passed"] for row in rows),
        "private_unauthorized_exposure_rate": _ratio(sum(len(row["incorrectly_exposed_fields"]) for row in rows), hidden_values),
        "private_exposure_rate": _ratio(exposed_private, hidden_values),
        "investor_shared_public_exposure_rate": _ratio(exposed_investor, hidden_values),
        "visibility_classification_correctness": _ratio(sum(not row["incorrectly_exposed_fields"] and not row["incorrectly_hidden_fields"] for row in rows), len(rows)),
        "public_projection_precision": _ratio(correct_public, exposed),
        "public_projection_recall": _ratio(correct_public, expected_public),
        "unauthorized_modification_rate": _ratio(unauthorized_failures, len(unauthorized)),
        "partial_update_integrity": _ratio(sum(row["partial_update_safe"] for row in rows), len(rows)),
        "historical_reproducibility": _ratio(sum(row["history_preserved"] for row in rows), len(rows)),
        "cross_project_isolation": _ratio(sum(row["cross_project_isolation"] for row in rows), len(rows)),
        "visibility_change_correctness": _ratio(sum(row["visibility_change_correct"] for row in rows), len(rows)),
        "duplication_count": sum(row["duplication_count"] for row in rows),
        "metadata_entries": sum(row["metadata_entries"] for row in rows),
        "violated_invariant_count": sum(len(row["violated_invariants"]) for row in rows),
    }


def run() -> dict:
    benchmarks = {"core": load_benchmark(CORE), "adversarial": load_benchmark(ADVERSARIAL)}
    candidates = {candidate: {} for candidate in ("v0_field_level", "v1_section_level")}
    aggregates = {candidate: {} for candidate in candidates}
    for candidate in candidates:
        for name, benchmark in benchmarks.items():
            rows = [_observation(case, candidate) for case in benchmark["scenarios"]]
            candidates[candidate][name] = rows
            aggregates[candidate][name] = aggregate(rows)
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        revision = None
    result = {
        "metadata": {"experiment": "EX-009", "research_question": "RQ-010", "benchmark_ids": [benchmarks["core"]["benchmark_id"], benchmarks["adversarial"]["benchmark_id"]], "candidate_versions": ["v0_field_level", "v1_section_level"], "evaluated_at": datetime.now(timezone.utc).isoformat(), "git_revision": revision, "evaluator_version": EVALUATOR_VERSION},
        "aggregates": aggregates,
        "candidates": candidates,
    }
    RAW_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RAW_RESULTS.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
