from __future__ import annotations

from app.modules.research.extraction_parser import SourceSegment, resolve_segment

from .contracts import ExtractiveExtraction, FIELDS


def resolve_extractive_values(extraction: ExtractiveExtraction, segments: tuple[SourceSegment, ...], source_version_id: str) -> tuple[dict[str, list[str]], dict[str, list[str]], int]:
    """Resolve model-selected IDs; factual values are copied only from source."""
    values: dict[str, list[str]] = {field: [] for field in FIELDS}
    ids_by_field: dict[str, list[str]] = {field: [] for field in FIELDS}
    invalid = 0
    for field in FIELDS:
        current = getattr(extraction, field)
        for item in current.items:
            try:
                for evidence_id in dict.fromkeys(item.evidence_ids):
                    segment = resolve_segment(segments, evidence_id, source_version_id)
                    values[field].append(segment.text)
                    ids_by_field[field].append(segment.segment_id)
            except ValueError:
                invalid += 1
    return values, ids_by_field, invalid


def build_abstract(values: dict[str, list[str]]) -> str:
    clauses: list[str] = []
    if values.get("research_problem"):
        clauses.append(f"This research addresses {values['research_problem'][0]}")
    if values.get("technologies") or values.get("methodology"):
        method = values.get("technologies", [])[:1] + values.get("methodology", [])[:1]
        clauses.append(f"It reports {'; '.join(method)}")
    if values.get("main_results"):
        clauses.append(f"The reported result is {values['main_results'][0]}")
    if values.get("explicit_applications"):
        clauses.append(f"The source states the application {values['explicit_applications'][0]}")
    return ". ".join(clauses) + ("." if clauses else "")


def abstract_factual_values(values: dict[str, list[str]], abstract: str) -> list[str]:
    return [value for field in FIELDS for value in values.get(field, []) if value and value not in abstract]
