import pytest
import httpx

from app.main import app
from app.modules.ai.schemas import AgentRunRequestTrace, AgentRunResponseTrace
from app.modules.ai.services import AgentRunService, _safe_error_message


@pytest.mark.asyncio
async def test_conversation_persistence_requires_authentication() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/conversations", json={"title": "anonymous"})

    assert response.status_code == 401


def test_error_redaction_removes_credentials_and_limits_length() -> None:
    message = "Authorization: Bearer abc123 password=secret " + ("x" * 2000)

    safe = _safe_error_message(message)

    assert "Bearer" not in safe
    assert "secret" not in safe
    assert len(safe) == 1000


def test_run_transition_graph_is_explicit() -> None:
    assert "running" in AgentRunService.TRANSITIONS["queued"]
    assert "succeeded" in AgentRunService.TRANSITIONS["running"]
    assert AgentRunService.TRANSITIONS["succeeded"] == set()


def test_trace_service_requires_explicit_pydantic_payloads() -> None:
    service = AgentRunService.__new__(AgentRunService)
    service.max_payload_bytes = 1024

    with pytest.raises(TypeError):
        service._json_payload({"authorization": "Bearer secret"})

    assert service._json_payload(AgentRunRequestTrace(intent="classify"))["intent"] == "classify"
    assert service._json_payload(AgentRunResponseTrace(summary="ok"))["summary"] == "ok"


def test_trace_payload_limit_rejects_oversized_safe_projection() -> None:
    service = AgentRunService.__new__(AgentRunService)
    service.max_payload_bytes = 10

    with pytest.raises(ValueError, match="exceeds"):
        service._json_payload(AgentRunResponseTrace(summary="too large"))
