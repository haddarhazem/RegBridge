"""Real OIDC/browser recovery acceptance; AI boundary mocked in the race test."""
import asyncio
import re
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.async_api import expect

from .conftest import authenticate, create_project, complete_onboarding

pytestmark = pytest.mark.browser_e2e


async def test_entrepreneur_pages_idle_history_and_cancel_race(browser_page, synthetic_user):
    page = browser_page
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    network = []
    inspections = []

    async def inspect_response(response):
        path = urlsplit(response.url).path
        if not path.startswith(('/projects', '/conversations', '/compliance', '/users/me')):
            return
        entry = {'path': re.sub(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', ':id', path),
                 'method': response.request.method, 'status': response.status}
        try:
            payload = await response.json()
            entry['shape'] = 'null' if payload is None else 'array' if isinstance(payload, list) else 'object' if isinstance(payload, dict) else type(payload).__name__
            if isinstance(payload, dict):
                entry['fields'] = sorted(payload.keys())
        except Exception:
            entry['shape'] = 'empty_or_cancelled'
        network.append(entry)

    page.on('response', lambda response: inspections.append(asyncio.create_task(inspect_response(response))))
    await authenticate(page, synthetic_user)
    await create_project(page)
    await complete_onboarding(page, {'activity': 'Synthetic SaaS pour clients professionnels'})
    for view in ["dashboard", "project", "roadmap", "documents", "regulatory", "contracts", "access"]:
        await page.goto(f"/entrepreneur/?view={view}")
        await expect(page.locator("body")).to_have_attribute("data-app-state", "ready")
        await expect(page.locator("[data-workspace] .inline-error")).to_have_count(0)
        await expect(page.locator("[data-workspace] h1")).to_be_visible()
    await page.locator("[data-open-copilot]").click()
    await expect(page.locator("[data-copilot-generating]")).to_be_hidden()
    await expect(page.locator("[data-submit-copilot]")).to_be_enabled()
    await expect(page.locator("[data-copilot-context-count]")).to_contain_text("6/6")
    await expect(page.locator("[data-copilot-drawer]")).to_have_attribute("role", "complementary")
    await expect(page.locator("[data-copilot-drawer]")).not_to_have_attribute("aria-modal", "true")
    await page.wait_for_timeout(300)  # Let the documented 220 ms dock transition settle.
    frame_box = await page.locator(".app-frame").bounding_box()
    drawer_box = await page.locator("[data-copilot-drawer]").bounding_box()
    assert frame_box and drawer_box and frame_box["x"] + frame_box["width"] <= drawer_box["x"] + 1
    await page.locator('[data-nav-view="roadmap"]').first.click()
    await expect(page.locator("body")).to_have_class(re.compile("copilot-open"))
    await expect(page.locator("[data-workspace] h1")).to_be_visible()

    # A persisted older thread never becomes active just by opening the drawer.
    await page.evaluate("""async () => {
      const api = window.RegBridgeEntrepreneurApi;
      const projects = await api.projects();
      const thread = await api.createConversation(projects[0].id, 'Previous synthetic conversation');
      await window.RegBridgeAuthRuntime.apiRequest(`/conversations/${thread.id}/messages`, {
        method: 'POST', body: JSON.stringify({content: 'bonjour historique synthétique'})
      });
    }""")
    await page.reload()
    await expect(page.locator("body")).to_have_attribute("data-app-state", "ready")
    await page.locator("[data-open-copilot]").click()
    await expect(page.locator("[data-copilot-messages]")).not_to_contain_text("bonjour")
    await page.locator("[data-show-copilot-history]").click()
    await expect(page.locator("[data-copilot-history]")).to_be_visible()
    await page.locator("[data-copilot-thread]").filter(has_text="Previous synthetic conversation").click()
    await expect(page.locator("[data-copilot-messages]")).to_contain_text("bonjour historique")
    await page.locator("[data-new-copilot]").click()
    await expect(page.locator("[data-copilot-messages]")).not_to_contain_text("bonjour")

    pending = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def respond(route):
        calls.append(route.request.post_data_json["content"])
        number = len(calls)
        if number == 1:
            pending.set()
            await release.wait()
        try:
            await route.fulfill(json={
                "user_message": {"id": f"user-{number}", "role": "user", "content": calls[number - 1]},
                "assistant_message": {"id": f"assistant-{number}", "role": "assistant", "content": f"Synthetic result {number}"},
            }, status=201)
        except Exception:
            if number != 1:
                raise

    await page.route("**/conversations/*/responses", respond)
    await page.locator("#copilot-question").fill("Synthetic question one")
    await page.locator("[data-submit-copilot]").click()
    await asyncio.wait_for(pending.wait(), 20)
    await expect(page.locator("[data-copilot-generating]")).to_be_visible()
    await expect(page.locator("[data-submit-copilot]")).to_be_disabled()
    await page.locator("[data-show-copilot-history]").click()
    await expect(page.locator("[data-copilot-history]")).to_be_visible()
    await page.locator("[data-copilot-thread]").filter(has_text="Previous synthetic conversation").click()
    await expect(page.locator("[data-copilot-messages]")).to_contain_text("bonjour historique")
    release.set()
    await expect(page.locator("[data-copilot-generating]")).to_be_hidden()
    await expect(page.locator("[data-submit-copilot]")).to_be_enabled()
    await expect(page.locator("[data-copilot-messages]")).not_to_contain_text("Synthetic result 1")
    await page.locator("[data-new-copilot]").click()
    await page.locator("#copilot-question").fill("Synthetic question two")
    await page.locator("[data-submit-copilot]").click()
    await expect(page.locator("[data-copilot-messages]")).to_contain_text("Synthetic result 2")
    response_calls = len(calls)
    await page.locator("[data-expand-copilot]").click()
    await expect(page.locator("[data-copilot-drawer]")).to_have_attribute("role", "dialog")
    await expect(page.locator("[data-copilot-messages]")).to_contain_text("Synthetic result 2")
    await page.locator("[data-expand-copilot]").click()
    await expect(page.locator("[data-copilot-drawer]")).to_have_attribute("role", "complementary")
    assert len(calls) == response_calls
    await page.locator("[data-close-copilot]").click()
    await page.locator("[data-open-copilot]").click()
    await expect(page.locator("[data-copilot-generating]")).to_be_hidden()
    await page.screenshot(path="artifacts/browser-e2e/copilot-recovery-desktop.png", animations='disabled')
    await page.set_viewport_size({"width": 390, "height": 844})
    assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    await page.screenshot(path="artifacts/browser-e2e/copilot-recovery-mobile.png", animations='disabled')
    await page.locator("[data-close-copilot]").click()
    await page.set_viewport_size({"width": 1440, "height": 900})
    await page.locator("[data-logout]").click()
    await page.wait_for_url(re.compile(r"/auth/login/"), timeout=30000)
    await authenticate(page, synthetic_user, register=False)
    await page.locator('[data-open-copilot]').click()
    await expect(page.locator('[data-copilot-generating]')).to_be_hidden()
    await expect(page.locator('[data-copilot-messages]')).not_to_contain_text('bonjour')
    await expect(page.locator('[data-copilot-messages]')).not_to_contain_text('Synthetic result')
    await page.locator('[data-close-copilot]').click()
    second = await page.evaluate("() => window.RegBridgeEntrepreneurApi.createProject({display_name: 'Second synthetic project', project_type: 'idea', raw_description: 'Synthetic second project'})")
    await page.goto(f"/entrepreneur/?view=project&project={second['id']}")
    await expect(page.locator('body')).to_have_attribute('data-app-state', 'ready')
    await page.locator('[data-open-copilot]').click()
    await expect(page.locator('[data-copilot-project]')).to_have_text('Second synthetic project')
    await expect(page.locator('[data-copilot-messages]')).not_to_contain_text('bonjour')
    await page.locator('[data-show-copilot-history]').click()
    await expect(page.locator('[data-copilot-notice]')).to_contain_text('Aucune conversation')
    await asyncio.gather(*inspections)
    Path('artifacts/browser-e2e/recovery-bootstrap-contracts.json').write_text(
        json.dumps({'synthetic_only': True, 'responses': network, 'js_errors': errors}, indent=2), encoding='utf-8')
    assert not [entry for entry in network if entry['status'] >= 500]
    assert not errors


async def test_regulatory_and_copilot_ui_recover_after_http_failure(browser_page, synthetic_user):
    page = browser_page
    await authenticate(page, synthetic_user)
    await create_project(page)
    await complete_onboarding(page, {'activity': 'Synthetic SaaS pour clients professionnels'})
    # Inferred proposals require an explicit decision before regulatory analysis.
    await page.locator('[data-nav-view="project"]').first.click()
    await expect(page.locator('[data-workspace]')).to_have_attribute('aria-busy', 'false')
    await page.locator('[data-tab="facts"]').click()
    await expect(page.locator('[data-workspace]')).to_have_attribute('aria-busy', 'false')
    while await page.locator('[data-action="reject-fact"]').count():
        async with page.expect_response(lambda response: response.request.method == 'DELETE' and '/facts/' in response.url):
            await page.locator('[data-action="reject-fact"]').first.click()
        await expect(page.locator('[data-workspace]')).to_have_attribute('aria-busy', 'false')
    await page.locator('[data-nav-view="regulatory"]').first.click()
    await expect(page.locator('[data-workspace]')).to_have_attribute('aria-busy', 'false')

    assessment_calls = 0

    async def fail_assessment(route):
        nonlocal assessment_calls
        if route.request.method != 'POST':
            await route.continue_()
            return
        assessment_calls += 1
        await route.fulfill(status=503, json={'detail': 'Synthetic provider failure'})

    await page.route('**/projects/*/assessments', fail_assessment)
    assessment_button = page.locator('[data-action="generate-assessment"]')
    await assessment_button.click()
    await expect(page.locator('.toast-error')).to_be_visible()
    await expect(assessment_button).to_be_enabled()
    assert assessment_calls == 1

    await page.locator('[data-open-copilot]').click()
    response_calls = 0

    async def recover_copilot(route):
        nonlocal response_calls
        response_calls += 1
        if response_calls == 1:
            await route.fulfill(status=503, json={'detail': 'Synthetic provider failure'})
            return
        content = route.request.post_data_json['content']
        await route.fulfill(status=201, json={
            'user_message': {'id': 'recovery-user', 'role': 'user', 'content': content},
            'assistant_message': {'id': 'recovery-assistant', 'role': 'assistant', 'content': 'Synthetic recovered response'},
        })

    await page.route('**/conversations/*/responses', recover_copilot)
    await page.locator('#copilot-question').fill('Synthetic failing question')
    await page.locator('[data-submit-copilot]').click()
    await expect(page.locator('[data-copilot-error]')).to_be_visible()
    await expect(page.locator('[data-copilot-generating]')).to_be_hidden()
    await expect(page.locator('[data-submit-copilot]')).to_be_enabled()
    await page.locator('#copilot-question').fill('Synthetic recovery question')
    await page.locator('[data-submit-copilot]').click()
    await expect(page.locator('[data-copilot-error]')).to_be_hidden()
    await expect(page.locator('[data-copilot-messages]')).to_contain_text('Synthetic recovered response')
    assert response_calls == 2


@pytest.mark.parametrize('action', ['stop-before-thread', 'switch', 'logout'])
async def test_pending_copilot_does_not_survive_navigation(browser_page, synthetic_user, action):
    """Real OIDC/project API, controlled pending AI boundary; no provider call."""
    page = browser_page
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    await authenticate(page, synthetic_user)
    await create_project(page)
    second = await page.evaluate("() => window.RegBridgeEntrepreneurApi.createProject({display_name: 'Other synthetic project', project_type: 'idea', raw_description: 'Synthetic isolation check'})")
    await page.reload()
    await expect(page.locator('body')).to_have_attribute('data-app-state', 'ready')
    pending = asyncio.Event()
    release = asyncio.Event()

    async def hold(route):
        if route.request.method != 'POST':
            await route.continue_()
            return
        pending.set()
        await release.wait()
        # Deliberately finish after the UI abandoned the operation. This is not
        # an assistant answer and must never enter a new active conversation.
        try:
            await route.fulfill(status=503, json={'detail': 'Synthetic delayed failure'})
        except Exception:
            pass  # Browser cancellation/navigation may already close the route.

    pattern = '**/conversations' if action == 'stop-before-thread' else '**/conversations/*/responses'
    await page.route(pattern, hold)
    await page.locator('[data-open-copilot]').click()
    await page.locator('#copilot-question').fill('Synthetic pending question')
    await page.locator('[data-submit-copilot]').click()
    await asyncio.wait_for(pending.wait(), 20)
    await expect(page.locator('[data-copilot-generating]')).to_be_visible()
    if action == 'stop-before-thread':
        await page.locator('[data-cancel-copilot]').click()
    elif action == 'close':
        await page.locator('[data-close-copilot]').click()
        await page.locator('[data-open-copilot]').click()
    elif action == 'navigate':
        # Exercise the existing navigation handler while an operation is pending.
        await page.locator('[data-nav-view="roadmap"]').first.evaluate('(link) => link.click()')
        await expect(page.locator('body')).to_have_attribute('data-app-state', 'ready')
    elif action == 'switch':
        await page.locator('[data-project-select]').select_option(second['id'])
        await expect(page.locator('[data-copilot-project]')).to_have_text('Other synthetic project')
    else:
        await page.locator('[data-logout]').evaluate('(button) => button.click()')
        await page.wait_for_url(re.compile(r'/auth/login/'), timeout=30000)
    release.set()
    if action == 'logout':
        await authenticate(page, synthetic_user, register=False)
        await page.locator('[data-open-copilot]').click()
    await expect(page.locator('[data-copilot-generating]')).to_be_hidden()
    await expect(page.locator('[data-submit-copilot]')).to_be_enabled()
    await expect(page.locator('[data-copilot-messages]')).not_to_contain_text('Synthetic pending question')
    await expect(page.locator('[data-copilot-error]')).not_to_contain_text('Synthetic delayed failure')
    assert not errors


@pytest.mark.skipif(os.getenv('ENTREPRENEUR_LIVE') != '1', reason='Explicit Gemini live authorization required')
async def test_one_synthetic_enersight_live_browser_turn(browser_page, synthetic_user):
    page = browser_page
    errors = []
    page.on('pageerror', lambda error: errors.append(type(error).__name__))
    await authenticate(page, synthetic_user)
    await create_project(page, description='Synthetic EnerSight SaaS de suivi énergétique pour PME françaises.')
    await complete_onboarding(page, {
        'activity': 'EnerSight : plateforme SaaS de suivi et optimisation énergétique pour les PME.',
        'sector': 'Efficacité énergétique', 'technology': 'Analyse de données et intelligence artificielle',
        'data': 'Factures énergétiques, données de compteurs, coordonnées professionnelles des utilisateurs.',
        'market': 'PME françaises', 'location': 'France',
    })
    await page.locator('[data-open-copilot]').click()
    await expect(page.locator('[data-copilot-generating]')).to_be_hidden()
    question = "Quelles sont les principales obligations réglementaires que je dois prendre en compte pour EnerSight concernant les données personnelles, l'intelligence artificielle et la sécurité de ma plateforme SaaS en France ?"
    await page.locator('#copilot-question').fill(question)
    async with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/responses'), timeout=190000) as pending:
        await page.locator('[data-submit-copilot]').click()
    response = await pending.value
    await expect(page.locator('[data-copilot-generating]')).to_be_hidden(timeout=10000)
    report = {'synthetic_only': True, 'http_status': response.status, 'request_id': response.headers.get('x-request-id'), 'js_errors': errors}
    if response.status == 201:
        turn = await response.json()
        report.update({'conversation_id': turn['conversation_id'], 'answer': turn['assistant_message']['content'],
                       'sources': turn['sources'], 'warnings': turn['warnings'], 'orchestration_status': turn['orchestration_status']})
        await expect(page.locator('.copilot-message-assistant > span').last).to_have_text(report['answer'])
        persisted = await page.evaluate('(id) => window.RegBridgeEntrepreneurApi.conversation(id)', turn['conversation_id'])
        report['persisted_exact'] = persisted['messages'][-1]['content'] == report['answer']
    else:
        report['visible_error'] = await page.locator('[data-copilot-error]').inner_text()
    Path('artifacts/browser-e2e/recovery-browser-live.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    await page.screenshot(path='artifacts/browser-e2e/recovery-browser-live.png')
    assert response.status == 201, f'Copilot HTTP {response.status}; safe report saved'
    assert report['sources'], 'No verified sourced answer; safe report saved'
    assert report['persisted_exact'] and not errors
