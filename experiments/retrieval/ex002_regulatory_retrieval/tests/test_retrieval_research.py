import json

import pytest

from ..contracts import BenchmarkItem
from ..metrics import evidence_coverage, precision_at_k, recall_at_k, reciprocal_rank
from ..qdrant_reader import ReadOnlyQdrantReader


def item(status="human_validated"):
    return BenchmarkItem.model_validate({"id": "REG-1", "question": "question", "topic": "topic", "annotation_status": status, "expected_evidence": [{"point_id": "p1"}]})


def point(point_id, score=0.9):
    return {"point_id": point_id, "score": score, "payload": {}}


def test_metrics_match_point_ids():
    values = [point("wrong"), point("p1"), point("other")]
    assert recall_at_k(item(), values[:2]) == 1.0
    assert precision_at_k(item(), values[:2]) == 0.5
    assert reciprocal_rank(item(), values) == 0.5
    assert evidence_coverage([item()], {"REG-1": values}) == 1.0


def test_benchmark_gate_rejects_unvalidated_items():
    pending = item("needs_human_validation")
    assert pending.annotation_status != "human_validated"
    with pytest.raises(ValueError):
        json.loads('{"annotation_status":"human_validated" trailing}')


def test_qdrant_reader_has_no_mutation_surface():
    forbidden = {"upsert", "delete", "set_payload", "create_payload_index", "update_collection", "recreate_collection"}
    assert forbidden.isdisjoint(dir(ReadOnlyQdrantReader))
