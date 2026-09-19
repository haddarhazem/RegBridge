"""One opt-in live authoritative-source request through the real HTTP stack.

This test intentionally uses browser/OIDC authentication and the persisted
Copilot status endpoint.  It records only trace metadata needed to diagnose
the fallback path; it never writes prompts, answers, excerpts, URLs, tokens,
or credentials to an artifact.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from playwright.async_api import expect

from .conftest import authenticate, complete_onboarding, create_project


pytestmark = pytest.mark.browser_e2e


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_AUTHORITATIVE_FALLBACK_TESTS") != "1",
    reason="Explicit live authoritative-fallback authorization required",
)
async def test_one_ai_question_records_authoritative_fallback_trace(browser_page, synthetic_user):
    """Exercise exactly one authorized AI question without exposing content."""

    page = browser_page
    await authenticate(page, synthetic_user)
    await create_project(
        page,
        description="Synthetic EnerSight SaaS for French SMEs to monitor energy consumption.",
    )
    await complete_onboarding(
        page,
        {
            "activity": "Synthetic EnerSight SaaS for French energy-efficiency SMEs.",
            "sector": "Energy efficiency",
            "technology": "Data analysis and artificial intelligence",
            "data": "Professional contact details and synthetic energy-meter data.",
            "market": "French SMEs",
            "location": "France",
        },
    )

    await page.locator("[data-open-copilot]").click()
    await expect(page.locator("[data-copilot-generating]")).to_be_hidden()
    await page.locator("#copilot-question").fill(
        "Quelles exigences de l'AI Act concernent précisément mon système d'IA ?"
    )

    async with page.expect_response(
        lambda response: response.request.method == "POST" and response.url.endswith("/responses"),
        timeout=240_000,
    ) as pending:
        await page.locator("[data-submit-copilot]").click()
    response = await pending.value
    request_id = response.headers.get("x-request-id")
    report: dict[str, object] = {
        "synthetic_only": True,
        "http_sent": True,
        "http_status": response.status,
        "request_id": request_id,
    }

    if response.status == 201 and request_id:
        turn = await response.json()
        conversation_id = turn["conversation_id"]
        status = await page.evaluate(
            """async ({ conversationId, requestId }) =>
                window.RegBridgeAuthRuntime.apiRequest(
                  `/conversations/${conversationId}/requests/${requestId}/status`
                )""",
            {"conversationId": conversation_id, "requestId": request_id},
        )
        diagnostics = status.get("diagnostics") or {}
        report.update(
            {
                "conversation_id": conversation_id,
                "backend_received": True,
                "root_trace_present": status.get("status") in {"completed", "failed", "cancelled"},
                "pipeline_status": status.get("status"),
                "stages": [
                    {
                        "stage": stage.get("stage"),
                        "status": stage.get("status"),
                        "duration_ms": stage.get("duration_ms"),
                    }
                    for stage in status.get("stages", [])
                ],
                "diagnostics": {
                    key: diagnostics.get(key)
                    for key in (
                        "required_domains",
                        "question_scope",
                        "initial_evidence_count",
                        "initial_evidence_status",
                        "initial_scope_supported",
                        "fallback_attempted",
                        "fallback_evidence_count",
                        "authoritative_fallback_attempted",
                        "authoritative_fallback_domains",
                        "authoritative_sources_attempted",
                        "authoritative_sources_succeeded",
                        "authoritative_sources_failed",
                        "authoritative_external_evidence_count",
                        "final_evidence_count",
                        "final_evidence_status",
                        "final_scope_supported",
                        "verification_verdict",
                    )
                },
                "user_facing_source_organizations": [
                    source.get("organization")
                    for source in turn.get("sources", [])
                    if isinstance(source, dict) and source.get("organization")
                ],
            }
        )

    artifact = Path("artifacts/browser-e2e/authoritative-fallback-ai-live.json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    assert response.status == 201, "Safe trace report was written before this assertion"
    assert request_id, "The HTTP response did not carry request correlation"
    assert report.get("root_trace_present"), "The persisted Copilot trace was not available"
    assert report.get("pipeline_status") == "completed", "The Copilot pipeline did not complete"
