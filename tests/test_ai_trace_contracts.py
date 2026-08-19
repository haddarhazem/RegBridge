import uuid

import pytest
from pydantic import ValidationError

from app.modules.ai.schemas import AgentRunRequestTrace, AgentRunResponseTrace, ModelTraceMetadata, TraceResourceRef


def test_trace_request_is_allowlisted_and_supports_research_metadata() -> None:
    trace = AgentRunRequestTrace(
        experiment_id="EX-002",
        configuration_version="orchestrator-comparison-v1",
        context_refs=[TraceResourceRef(resource_type="document", resource_id=uuid.uuid4(), version_id=uuid.uuid4())],
    )

    assert trace.model_dump(mode="json")["experiment_id"] == "EX-002"
    assert "configuration_version" in trace.model_dump()


def test_trace_contract_rejects_unknown_fields_and_raw_private_content() -> None:
    with pytest.raises(ValidationError):
        AgentRunRequestTrace(full_document_text="private document")

    with pytest.raises(ValidationError):
        ModelTraceMetadata(api_key="secret")


def test_trace_response_and_model_metadata_are_structured() -> None:
    response = AgentRunResponseTrace(summary="safe", result={"count": 1})
    metadata = ModelTraceMetadata(provider="provider-neutral", model="test-model", max_output_tokens=100)

    assert response.result == {"count": 1}
    assert metadata.provider == "provider-neutral"
