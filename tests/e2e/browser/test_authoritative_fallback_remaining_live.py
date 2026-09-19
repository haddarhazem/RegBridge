"""Opt-in browser acceptance for the remaining authorized official domains."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from playwright.async_api import expect

from .conftest import authenticate, complete_onboarding, create_project


pytestmark = pytest.mark.browser_e2e


async def _run_live_case(browser_page, synthetic_user, *, name: str, question: str, domain: str, scope: str) -> None:
    page = browser_page
    await authenticate(page, synthetic_user)
    await create_project(
        page,
        description="Synthetic EnerSight SaaS for French SMEs to monitor energy consumption.",
    )
    await complete_onboarding(
        page,
        {
            "activity": "EnerSight : plateforme SaaS synthétique de suivi énergétique pour PME françaises.",
            "sector": "Efficacité énergétique",
            "technology": "Analyse de données et intelligence artificielle",
            "data": "Données de contact professionnelles et données synthétiques de compteurs énergétiques.",
            "market": "PME françaises",
            "location": "France",
        },
    )
    await page.locator("[data-open-copilot]").click()
    await expect(page.locator("[data-copilot-generating]")).to_be_hidden()
    await page.locator("#copilot-question").fill(question)

    async with page.expect_response(
        lambda response: response.request.method == "POST" and response.url.endswith("/responses"),
        timeout=240_000,
    ) as pending:
        await page.locator("[data-submit-copilot]").click()
    response = await pending.value
    request_id = response.headers.get("x-request-id")
    report: dict[str, object] = {
        "synthetic_only": True,
        "http_status": response.status,
        "request_id": request_id,
    }

    if response.status == 201 and request_id:
        turn = await response.json()
        status = await page.evaluate(
            """async ({ conversationId, requestId }) =>
                window.RegBridgeAuthRuntime.apiRequest(
                  `/conversations/${conversationId}/requests/${requestId}/status`
                )""",
            {"conversationId": turn["conversation_id"], "requestId": request_id},
        )
        diagnostics = status.get("diagnostics") or {}
        report.update(
            {
                "pipeline_status": status.get("status"),
                "stages": [
                    {"stage": item.get("stage"), "status": item.get("status"), "duration_ms": item.get("duration_ms")}
                    for item in status.get("stages", [])
                ],
                "diagnostics": {
                    key: diagnostics.get(key)
                    for key in (
                        "required_domains",
                        "question_scope",
                        "initial_evidence_status",
                        "fallback_attempted",
                        "authoritative_fallback_attempted",
                        "authoritative_sources_attempted",
                        "authoritative_sources_succeeded",
                        "authoritative_sources_failed",
                        "authoritative_external_evidence_count",
                        "final_evidence_status",
                        "final_scope_supported",
                        "verification_verdict",
                    )
                },
            }
        )

    artifact = Path(f"artifacts/browser-e2e/authoritative-fallback-{name}-live.json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    assert response.status == 201, "Safe trace report was written before this assertion"
    assert request_id
    assert report.get("pipeline_status") == "completed"
    diagnostics = report.get("diagnostics", {})
    assert diagnostics.get("required_domains") == [domain]
    assert diagnostics.get("question_scope") == scope


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_AUTHORITATIVE_FALLBACK_TESTS") != "1",
    reason="Explicit live authoritative-fallback authorization required",
)
async def test_iot_energy_authoritative_fallback_live(browser_page, synthetic_user):
    await _run_live_case(
        browser_page,
        synthetic_user,
        name="iot-energy",
        question="Existe-t-il des obligations sectorielles spécifiques pour mes compteurs IoT énergétiques ?",
        domain="ENERGY_IOT",
        scope="SECTOR_SPECIFIC",
    )


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_AUTHORITATIVE_FALLBACK_TESTS") != "1",
    reason="Explicit live authoritative-fallback authorization required",
)
async def test_cloud_cybersecurity_authoritative_fallback_live(browser_page, synthetic_user):
    await _run_live_case(
        browser_page,
        synthetic_user,
        name="cloud-cybersecurity",
        question="Quelles obligations de cybersécurité s'appliquent à mon SaaS cloud ?",
        domain="SECURITY_CLOUD",
        scope="PROJECT_SPECIFIC",
    )
