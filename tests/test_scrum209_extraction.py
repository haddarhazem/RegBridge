import pytest

from app.modules.research.extraction import ExtractiveExtraction, build_abstract, resolve_selection
from app.modules.research.extraction_parser import parse_source, segment_source


def empty_fields():
    return {field: {"status": "NOT_AVAILABLE", "items": []} for field in ("domains", "technologies", "research_problem", "methodology", "main_results", "explicit_applications", "keywords", "limitations")}


def test_provider_contract_forbids_factual_values():
    payload = empty_fields()
    payload["main_results"] = {"status": "SUPPORTED", "items": [{"evidence_ids": ["SRC-001"], "value": "93.2%"}]}
    with pytest.raises(ValueError):
        ExtractiveExtraction.model_validate(payload)


def test_exact_copy_and_deterministic_abstract():
    parsed = parse_source("doc-v1", "text/plain", b"The method uses controlled testing.\nThe result is 93.2%.")
    extraction = ExtractiveExtraction.model_validate({**empty_fields(), "methodology": {"status": "SUPPORTED", "items": [{"evidence_ids": ["SRC-001"]}]}, "main_results": {"status": "SUPPORTED", "items": [{"evidence_ids": ["SRC-002"]}]}})
    values, refs = resolve_selection(extraction, segment_source(parsed), "doc-v1")
    assert values["main_results"] == ["The result is 93.2%."]
    assert refs["main_results"][0].document_version_id == "doc-v1"
    assert "93.2%" in build_abstract(values)


def test_supported_requires_evidence_and_not_available_has_none():
    payload = empty_fields()
    payload["domains"] = {"status": "SUPPORTED", "items": []}
    with pytest.raises(ValueError):
        ExtractiveExtraction.model_validate(payload)
    payload = empty_fields()
    payload["domains"] = {"status": "NOT_AVAILABLE", "items": [{"evidence_ids": ["SRC-001"]}]}
    with pytest.raises(ValueError):
        ExtractiveExtraction.model_validate(payload)
