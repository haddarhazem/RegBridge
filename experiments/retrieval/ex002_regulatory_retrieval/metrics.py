from __future__ import annotations

from collections.abc import Iterable

from .contracts import BenchmarkItem


def _matches(item: BenchmarkItem, point: dict) -> bool:
    for expected in item.expected_evidence:
        if expected.point_id and expected.point_id == str(point.get("point_id")):
            return True
        if expected.point_id:
            continue
        payload = point.get("payload", {})
        locators = [expected.source_domain, expected.url, expected.parent_url, expected.chunk_index]
        actual = [payload.get("source_domain"), payload.get("url"), payload.get("parent_url"), payload.get("chunk_index")]
        if any(value is not None for value in locators) and all(value is None or value == actual[index] for index, value in enumerate(locators)):
            return True
    return False


def recall_at_k(item: BenchmarkItem, points: list[dict]) -> float:
    expected = len(item.expected_evidence)
    return 0.0 if expected == 0 else sum(_matches(item, point) for point in points) / expected


def precision_at_k(item: BenchmarkItem, points: list[dict]) -> float:
    return 0.0 if not points else sum(_matches(item, point) for point in points) / len(points)


def reciprocal_rank(item: BenchmarkItem, points: list[dict]) -> float:
    for index, point in enumerate(points, start=1):
        if _matches(item, point):
            return 1 / index
    return 0.0


def evidence_coverage(items: Iterable[BenchmarkItem], retrieved: dict[str, list[dict]]) -> float:
    items = list(items)
    if not items:
        return 0.0
    return sum(recall_at_k(item, retrieved.get(item.id, [])) > 0 for item in items) / len(items)

