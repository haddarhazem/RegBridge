import logging
import uuid
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.core.observability import MetricsRegistry, emit_event, metrics
from app.main import app
from app.modules.ai.llm import LLMGenerationRequest, LLMMessage
from app.modules.ai.providers.mistral import MistralLLMProvider
from app.modules.regulatory.retrieval import RegulatoryRetriever, RegulatoryRetrievalError


@pytest.fixture(autouse=True)
def clean_metrics():
    metrics.reset()
    yield
    metrics.reset()


def test_structured_event_redacts_synthetic_secrets_and_private_content(caplog):
    caplog.set_level(logging.INFO, logger="regbridge.observability")
    emit_event(
        "test.failure",
        request_id=str(uuid.uuid4()),
        prompt="RB_OBS_PRIVATE_DOC_X81Q",
        api_key="RB_OBS_APIKEY_Z72P",
        authorization="Bearer RB_OBS_BEARER_T61M",
        content="RB_OBS_PRIVATE_RAG_C54K",
    )
    rendered = " ".join(record.getMessage() for record in caplog.records)
    assert "RB_OBS_PRIVATE_DOC_X81Q" not in rendered
    assert "RB_OBS_APIKEY_Z72P" not in rendered
    assert "RB_OBS_BEARER_T61M" not in rendered
    assert "RB_OBS_PRIVATE_RAG_C54K" not in rendered
    assert "[REDACTED]" in rendered


def test_metrics_use_bounded_labels_and_no_resource_ids():
    registry = MetricsRegistry()
    registry.increment("requests", component="http", request_id="private-id", project_id="private-project", route_template="/projects/{project_id}")
    snapshot = registry.snapshot()
    assert snapshot["counters"][0]["labels"] == {"component": "http", "route_template": "/projects/{project_id}"}
    assert "private-id" not in str(snapshot)
    assert "private-project" not in str(snapshot)


@pytest.mark.asyncio
async def test_request_id_is_returned_and_metrics_endpoint_is_safe():
    supplied = str(uuid.uuid4())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-ID": supplied})
        report = await client.get("/metrics")
    assert response.headers["X-Request-ID"] == supplied
    assert response.status_code in {200, 503}
    assert report.status_code == 200
    assert supplied not in report.text
    assert "counters" in report.json()


@pytest.mark.asyncio
async def test_qdrant_failure_is_localized_without_chunk_logging():
    class FailingEmbedder:
        def encode(self, question):
            raise TimeoutError("RB_OBS_PRIVATE_RAG_C54K")

    retriever = RegulatoryRetriever(embedder=FailingEmbedder(), client=SimpleNamespace(), collection="reglementation_chunks")
    with pytest.raises(RegulatoryRetrievalError):
        await retriever.retrieve("question")
    qdrant_events = [item for item in metrics.snapshot()["counters"] if item["labels"].get("dependency") == "qdrant"]
    assert qdrant_events and qdrant_events[0]["labels"]["status"] == "error"
    assert "RB_OBS_PRIVATE_RAG_C54K" not in str(metrics.snapshot())


@pytest.mark.asyncio
async def test_llm_failure_is_localized_without_provider_secret(caplog):
    class FailingClient:
        chat = None

        async def complete_async(self, **kwargs):
            raise TimeoutError("authorization: RB_OBS_APIKEY_Z72P")

    client = FailingClient()
    client.chat = client
    provider = MistralLLMProvider(api_key=SecretStr("RB_OBS_APIKEY_Z72P"), model="mistral-test", client=client)
    with pytest.raises(Exception):
        await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content="hello")], operation="test"))
    assert "RB_OBS_APIKEY_Z72P" not in " ".join(record.getMessage() for record in caplog.records)
    assert any(item["labels"].get("dependency") == "mistral" for item in metrics.snapshot()["counters"])
