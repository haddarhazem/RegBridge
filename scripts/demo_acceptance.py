"""Opt-in real local demo journey. No response mocking or direct database writes.

Creates only synthetic data via the product. Credentials stay in .env.demo.local.
Run from the repository root: python -m scripts.demo_acceptance setup
"""
from __future__ import annotations

import asyncio
import json
import importlib.util
import os
from pathlib import Path
import re
import secrets
import sys
import traceback
from urllib.parse import urlsplit

from dotenv import dotenv_values
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('demo_browser_helpers', ROOT / 'tests/e2e/browser/conftest.py')
_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers)
authenticate, complete_onboarding = _helpers.authenticate, _helpers.complete_onboarding
OUT = ROOT / "artifacts/browser-e2e"
CREDS = ROOT / ".env.demo.local"
FACTS = {
    "activity": "EnerSight Demo est un service SaaS fictif qui aide les PME à mesurer et réduire leur consommation énergétique.",
    "sector": "Logiciels de gestion énergétique",
    "technology": "Plateforme SaaS, compteurs connectés et algorithmes d'analyse de consommation.",
    "data": "Factures d'électricité et de gaz, relevés de compteurs, données de bâtiments et coordonnées professionnelles des utilisateurs. Données entièrement synthétiques pour la démonstration.",
    "target_market": "PME françaises",
    "location": "France",
}
CONTRACT = """CONTRAT SYNTHETIQUE DE DEMONSTRATION - AUCUNE PARTIE REELLE
Entre EnerSight Demo et Client Demo.
Article 1 - Objet. EnerSight Demo fournit un tableau de bord de consommation énergétique au Client Demo.
Article 2 - Durée. Le contrat est conclu pour douze mois à compter du 1 octobre 2026.
Article 3 - Prix. Le prix mensuel est de 100 euros hors taxes, payable dans les trente jours suivant la facture.
Article 4 - Confidentialité. Les parties gardent confidentielles les informations reçues pendant la prestation.
Article 5 - Résiliation. Chaque partie peut résilier avec un préavis écrit de trente jours.
Article 6 - Données. Les coordonnées professionnelles sont utilisées uniquement pour gérer le service.
"""


async def ready(page):
    await expect(page.locator('[data-workspace]')).to_have_attribute('aria-busy', 'false', timeout=30_000)


async def nav(page, name):
    await page.locator(f'[data-nav-view="{name}"]').first.click()
    await ready(page)


async def quiet(page):
    """Let UI follow-up reads finish before a deliberate reload or browser close."""
    for _ in range(100):
        await page.wait_for_timeout(100)
        if not page.demo_pending:
            await page.wait_for_timeout(200)
            if not page.demo_pending:
                return
    raise AssertionError('Product requests did not settle')


async def run(stage):
    if os.environ.get("DEMO_ACCEPTANCE") != "1":
        raise SystemExit("Explicit opt-in required: DEMO_ACCEPTANCE=1")
    OUT.mkdir(parents=True, exist_ok=True)
    fresh = not CREDS.exists()
    if fresh:
        # Runtime credential artifact, never a fixture or tracked source file.
        CREDS.write_text("DEMO_EMAIL=enersight-demo@regbridge.example\nDEMO_PASSWORD=" + secrets.token_urlsafe(32) + "!Aa9\n", encoding="utf-8")
    local = dotenv_values(CREDS)
    user = {"email": local["DEMO_EMAIL"], "password": local["DEMO_PASSWORD"]}
    record = {"stage": stage, "http": [], "page_errors": [], "failed_requests": []}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(base_url="http://127.0.0.1:8000", viewport={"width":1440,"height":1000})
        page = await context.new_page()
        page.demo_pending = set()
        def business_request(request):
            return urlsplit(request.url).path.startswith(("/projects", "/documents", "/conversations", "/compliance"))
        page.on('request', lambda request: page.demo_pending.add(request) if business_request(request) else None)
        page.on('requestfinished', lambda request: page.demo_pending.discard(request))
        page.on('requestfailed', lambda request: page.demo_pending.discard(request))
        # Never capture OAuth URLs, headers, payloads, tokens or authentication screens.
        def observe(response):
            path = urlsplit(response.url).path
            if path.startswith(("/projects", "/documents", "/conversations", "/compliance")):
                record["http"].append({"method":response.request.method,"path":path,"status":response.status})
        page.on("response", observe)
        page.on("pageerror", lambda _: record["page_errors"].append("uncaught JavaScript exception"))
        page.on("requestfailed", lambda request: record["failed_requests"].append(urlsplit(request.url).path) if urlsplit(request.url).path.startswith(("/projects", "/documents", "/conversations")) else None)
        authenticated = False
        try:
            await authenticate(page, user, register=fresh)
            authenticated = True
            await ready(page)
            projects = await page.evaluate('() => window.RegBridgeEntrepreneurApi.projects()')
            demo = next((p for p in projects if p['display_name']=='EnerSight Demo'), None)
            if not demo:
                await page.get_by_role('button', name=re.compile('premier projet', re.I)).click()
                await page.get_by_label('Nom du projet').fill('EnerSight Demo')
                await page.locator('textarea[name="raw_description"]').fill(FACTS['activity'])
                await page.locator('[data-action="submit-create"]').click()
                await expect(page.locator('[data-project-switcher]')).to_contain_text('EnerSight Demo')
            else:
                selector = page.locator('[data-project-switcher] select')
                if await selector.count():
                    await selector.select_option(demo['id'])
                await ready(page)
            await complete_onboarding(page, FACTS)
            projects = await page.evaluate('() => window.RegBridgeEntrepreneurApi.projects()')
            project = next(p for p in projects if p['display_name']=='EnerSight Demo')
            if any(project.get(k) != v for k,v in FACTS.items()):
                await page.evaluate('(args) => window.RegBridgeEntrepreneurApi.updateOnboarding(args.id, {...args.facts, confirm:Object.keys(args.facts)})', {'id':project['id'],'facts':FACTS})
                await page.reload()
                await ready(page)
            record['project_id'] = project['id']
            record['project_type'] = project['project_type']
            if project['project_type'] != 'idea':
                await nav(page, 'dashboard')
                record['dashboard_idea_only_actions'] = await page.locator('[data-action="open-onboarding"]').count()
                assert record['dashboard_idea_only_actions'] == 0
            if stage == 'recovery':
                question = 'Quelles sont les principales obligations réglementaires pour mon projet en France ?'
                drawer = page.locator('[data-copilot-drawer]')
                await page.locator('[data-open-copilot]').click()
                await expect(drawer).to_have_attribute('role', 'complementary')
                await expect(drawer).not_to_have_attribute('aria-modal', 'true')
                await page.wait_for_timeout(300)
                frame_box = await page.locator('.app-frame').bounding_box()
                drawer_box = await drawer.bounding_box()
                record['docked'] = {
                    'width': drawer_box['width'] if drawer_box else None,
                    'workspace_reflowed': bool(frame_box and drawer_box and frame_box['x'] + frame_box['width'] <= drawer_box['x'] + 1),
                    'role': await drawer.get_attribute('role'),
                    'aria_modal': await drawer.get_attribute('aria-modal'),
                }

                response_count_before = sum(item['method'] == 'POST' and item['path'].endswith('/responses') for item in record['http'])
                await page.locator('#copilot-question').fill(question)
                async with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/responses'), timeout=300_000) as response:
                    await page.locator('[data-submit-copilot]').click()
                    await expect(page.locator('[data-copilot-messages]')).to_contain_text(question)
                    await expect(page.locator('[data-copilot-generating]')).to_be_visible()
                copilot_response = await response.value
                copilot_payload = await copilot_response.json()
                conversation_match = re.search(r'/conversations/([0-9a-f-]+)/responses$', urlsplit(copilot_response.url).path)
                conversation_id = conversation_match.group(1) if conversation_match else None
                assistant_content = copilot_payload.get('assistant_message', {}).get('content', '') if isinstance(copilot_payload, dict) else ''
                await expect(page.locator('[data-copilot-generating]')).to_be_hidden()
                await expect(page.locator('[data-submit-copilot]')).to_be_enabled()
                record['copilot'] = {
                    'http': copilot_response.status,
                    'conversation_id': conversation_id,
                    'orchestration_status': copilot_payload.get('orchestration_status') if isinstance(copilot_payload, dict) else None,
                    'warnings': copilot_payload.get('warnings') if isinstance(copilot_payload, dict) else None,
                    'answer_chars': len(assistant_content),
                    'frontend_error': (await page.locator('[data-copilot-error]').text_content() or '').strip(),
                    'loading_cleared': await page.locator('[data-copilot-generating]').is_hidden(),
                    'input_enabled': await page.locator('[data-submit-copilot]').is_enabled(),
                }
                if assistant_content:
                    await expect(page.locator('[data-copilot-messages]')).to_contain_text(assistant_content)

                await nav(page, 'roadmap')
                record['navigation'] = {
                    'roadmap_open': 'copilot-open' in (await page.locator('body').get_attribute('class') or ''),
                    'roadmap_conversation_preserved': not assistant_content or assistant_content in (await page.locator('[data-copilot-messages]').inner_text()),
                }
                await nav(page, 'regulatory')
                record['navigation']['regulatory_open'] = 'copilot-open' in (await page.locator('body').get_attribute('class') or '')
                record['navigation']['regulatory_conversation_preserved'] = not assistant_content or assistant_content in (await page.locator('[data-copilot-messages]').inner_text())

                assessment_button = page.locator('[data-action="generate-assessment"]')
                async with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/assessments'), timeout=300_000) as response:
                    await assessment_button.click()
                    await expect(assessment_button).to_be_disabled()
                assessment_response = await response.value
                assessment_payload = await assessment_response.json()
                await ready(page)
                assessment_result = assessment_payload.get('result', {}) if isinstance(assessment_payload, dict) else {}
                record['assessment'] = {
                    'http': assessment_response.status,
                    'id': assessment_payload.get('id'),
                    'version': assessment_payload.get('version'),
                    'status': assessment_payload.get('status'),
                    'verification_verdict': assessment_payload.get('verification_verdict'),
                    'verification_reasons': assessment_payload.get('verification_reasons'),
                    'counts': {key: len(assessment_result.get(key, [])) for key in ('obligations', 'recommendations', 'uncertainties', 'sources')},
                    'frontend_error': (await page.locator('.toast-error').text_content() or '').strip() if await page.locator('.toast-error').count() else '',
                }
                record['navigation']['assessment_copilot_open'] = 'copilot-open' in (await page.locator('body').get_attribute('class') or '')
                record['navigation']['assessment_conversation_preserved'] = not assistant_content or assistant_content in (await page.locator('[data-copilot-messages]').inner_text())
                if assessment_payload.get('status') == 'completed':
                    await expect(page.locator('[data-workspace]')).to_contain_text(f"Version {assessment_payload['version']}")
                    for heading in ('Obligations identifiées', 'Actions recommandées', 'Points à vérifier', 'Sources'):
                        await expect(page.locator('[data-workspace]')).to_contain_text(heading)

                # Make the just-completed turn historical explicitly, then restore it.
                if conversation_id and assistant_content:
                    await page.locator('[data-new-copilot]').click()
                    await expect(page.locator('[data-copilot-messages]')).not_to_contain_text(assistant_content)
                    async with page.expect_response(lambda r: r.request.method == 'GET' and urlsplit(r.url).path == '/conversations'):
                        await page.locator('[data-show-copilot-history]').click()
                    await expect(page.locator('[data-copilot-history]')).to_be_visible()
                    history_entries = page.locator('[data-copilot-thread]')
                    project_threads = await page.evaluate('(id) => window.RegBridgeEntrepreneurApi.conversations(id)', project['id'])
                    record['history'] = {
                        'count': await history_entries.count(),
                        'all_project_scoped': bool(project_threads) and all(item.get('subject_type') == 'project' and item.get('subject_id') == project['id'] for item in project_threads),
                        'contains_current': any(item.get('id') == conversation_id for item in project_threads),
                    }
                    historical = page.locator(f'[data-copilot-thread="{conversation_id}"]')
                    async with page.expect_response(lambda r: r.request.method == 'GET' and urlsplit(r.url).path == f'/conversations/{conversation_id}'):
                        await historical.click()
                    await expect(page.locator('[data-copilot-messages]')).to_contain_text(assistant_content)
                    record['history']['messages_restored'] = True
                    provider_requests = sum(item['method'] == 'POST' and item['path'].endswith('/responses') for item in record['http'])
                    await page.locator('[data-expand-copilot]').click()
                    await expect(drawer).to_have_attribute('role', 'dialog')
                    await expect(page.locator('[data-copilot-messages]')).to_contain_text(assistant_content)
                    await page.locator('[data-expand-copilot]').click()
                    await expect(drawer).to_have_attribute('role', 'complementary')
                    await expect(page.locator('[data-copilot-messages]')).to_contain_text(assistant_content)
                    record['fullscreen'] = {
                        'same_conversation': True,
                        'extra_provider_requests': sum(item['method'] == 'POST' and item['path'].endswith('/responses') for item in record['http']) - provider_requests,
                    }
                    await page.locator('[data-close-copilot]').click()
                    await expect(drawer).to_have_attribute('aria-hidden', 'true')
                    await page.locator('[data-open-copilot]').click()
                    await expect(page.locator('[data-copilot-messages]')).to_contain_text(assistant_content)
                    record['close_reopen_preserved'] = True
                    await page.locator('[data-new-copilot]').click()
                    await expect(page.locator('[data-copilot-messages]')).not_to_contain_text(assistant_content)
                    record['history']['new_conversation_clean'] = True
                else:
                    record['history'] = {'count': 0, 'all_project_scoped': False, 'contains_current': False, 'messages_restored': False, 'new_conversation_clean': False}
                    record['fullscreen'] = {'same_conversation': False, 'extra_provider_requests': None}
                    record['close_reopen_preserved'] = False

                record['copilot']['response_requests'] = sum(item['method'] == 'POST' and item['path'].endswith('/responses') for item in record['http']) - response_count_before
                await page.screenshot(path=str(OUT / 'demo-recovery-docked.png'), animations='disabled')

                # Accepted roadmap behavior gets only the requested persistence smoke.
                await page.locator('[data-close-copilot]').click()
                await nav(page, 'roadmap')
                roadmap_status = page.locator('[data-roadmap-item]').first
                record['roadmap_smoke'] = {'available': await roadmap_status.count() > 0, 'persisted': False}
                if record['roadmap_smoke']['available']:
                    current_status = await roadmap_status.input_value()
                    expected_status = 'in_progress' if current_status != 'in_progress' else 'completed'
                    async with page.expect_response(lambda r: r.request.method == 'PATCH' and '/roadmaps/' in r.url):
                        await roadmap_status.select_option(expected_status)
                    await quiet(page)
                    await page.reload()
                    await ready(page)
                    await expect(page.locator('[data-roadmap-item]').first).to_have_value(expected_status)
                    record['roadmap_smoke']['persisted'] = True

                assert copilot_response.status == 201 and assistant_content
                assert copilot_payload.get('orchestration_status') == 'succeeded' and not copilot_payload.get('warnings')
                assert record['copilot']['response_requests'] == 1
                assert assessment_response.status == 200
                assert assessment_payload.get('status') == 'completed'
                assert assessment_payload.get('verification_verdict') in ('pass', 'pass_with_warnings')
                assert assessment_result.get('obligations') and assessment_result.get('recommendations') and assessment_result.get('sources')
                assert all(record['navigation'].values())
                assert record['docked']['workspace_reflowed'] and 400 <= record['docked']['width'] <= 480
                assert record['history']['all_project_scoped'] and record['history']['contains_current'] and record['history']['messages_restored']
                assert record['history']['new_conversation_clean'] and record['fullscreen']['same_conversation']
                assert record['fullscreen']['extra_provider_requests'] == 0 and record['close_reopen_preserved']
                assert record['roadmap_smoke']['persisted']
            if stage == 'recovery-ui':
                drawer = page.locator('[data-copilot-drawer]')
                response_requests_before = sum(item['method'] == 'POST' and item['path'].endswith('/responses') for item in record['http'])
                await page.locator('[data-open-copilot]').click()
                await expect(drawer).to_have_attribute('role', 'complementary')
                await expect(drawer).not_to_have_attribute('aria-modal', 'true')
                await page.wait_for_timeout(300)
                frame_box = await page.locator('.app-frame').bounding_box()
                drawer_box = await drawer.bounding_box()
                record['docked'] = {
                    'width': drawer_box['width'] if drawer_box else None,
                    'workspace_reflowed': bool(frame_box and drawer_box and frame_box['x'] + frame_box['width'] <= drawer_box['x'] + 1),
                    'old_thread_auto_opened': bool(await page.locator('.copilot-message').count()),
                }
                async with page.expect_response(lambda r: r.request.method == 'GET' and urlsplit(r.url).path == '/conversations'):
                    await page.locator('[data-show-copilot-history]').click()
                await expect(page.locator('[data-copilot-history]')).to_be_visible()
                project_threads = await page.evaluate('(id) => window.RegBridgeEntrepreneurApi.conversations(id)', project['id'])
                restored = None
                for item in project_threads:
                    candidate = await page.evaluate('(id) => window.RegBridgeEntrepreneurApi.conversation(id)', item['id'])
                    if any(message.get('role') == 'assistant' and message.get('content') for message in candidate.get('messages', [])):
                        restored = candidate
                        break
                assert restored is not None, 'No existing persisted EnerSight assistant thread is available for history acceptance'
                assistant_content = next(message['content'] for message in restored['messages'] if message.get('role') == 'assistant' and message.get('content'))
                historical = page.locator(f'[data-copilot-thread="{restored["id"]}"]')
                async with page.expect_response(lambda r: r.request.method == 'GET' and urlsplit(r.url).path == f'/conversations/{restored["id"]}'):
                    await historical.click()
                await expect(page.locator('[data-copilot-messages]')).to_contain_text(assistant_content)
                record['history'] = {
                    'count': len(project_threads),
                    'all_project_scoped': bool(project_threads) and all(item.get('subject_type') == 'project' and item.get('subject_id') == project['id'] for item in project_threads),
                    'restored_thread_id': restored['id'],
                    'message_count': len(restored['messages']),
                    'messages_restored': True,
                }

                draft = 'Brouillon de navigation — ne pas envoyer'
                await page.locator('#copilot-question').fill(draft)
                record['navigation'] = {}
                for view in ('roadmap', 'regulatory', 'contracts'):
                    await nav(page, view)
                    record['navigation'][view] = {
                        'copilot_open': 'copilot-open' in (await page.locator('body').get_attribute('class') or ''),
                        'conversation_preserved': assistant_content in (await page.locator('[data-copilot-messages]').inner_text()),
                        'draft_preserved': await page.locator('#copilot-question').input_value() == draft,
                        'workspace_visible': await page.locator('[data-workspace] h1').is_visible(),
                    }

                await page.locator('[data-expand-copilot]').click()
                await expect(drawer).to_have_attribute('role', 'dialog')
                await expect(page.locator('[data-copilot-messages]')).to_contain_text(assistant_content)
                await page.locator('[data-expand-copilot]').click()
                await expect(drawer).to_have_attribute('role', 'complementary')
                await expect(page.locator('[data-copilot-messages]')).to_contain_text(assistant_content)
                await page.locator('[data-close-copilot]').click()
                await expect(drawer).to_have_attribute('aria-hidden', 'true')
                await page.locator('[data-open-copilot]').click()
                await expect(page.locator('[data-copilot-messages]')).to_contain_text(assistant_content)
                record['presentation'] = {
                    'fullscreen_same_thread': True,
                    'reduce_same_thread': True,
                    'close_reopen_same_thread': True,
                    'extra_provider_requests': sum(item['method'] == 'POST' and item['path'].endswith('/responses') for item in record['http']) - response_requests_before,
                }
                await page.locator('[data-new-copilot]').click()
                await expect(page.locator('[data-copilot-messages]')).not_to_contain_text(assistant_content)
                record['history']['new_conversation_clean'] = True
                await page.screenshot(path=str(OUT / 'demo-recovery-ui-docked.png'), animations='disabled')

                await page.locator('[data-close-copilot]').click()
                await nav(page, 'roadmap')
                roadmap_status = page.locator('[data-roadmap-item]').first
                record['roadmap_smoke'] = {'available': await roadmap_status.count() > 0, 'persisted': False}
                if record['roadmap_smoke']['available']:
                    await roadmap_status.locator('xpath=ancestor::details/summary').click()
                    current_status = await roadmap_status.input_value()
                    expected_status = 'in_progress' if current_status != 'in_progress' else 'completed'
                    async with page.expect_response(lambda r: r.request.method == 'PATCH' and '/roadmaps/' in r.url):
                        await roadmap_status.select_option(expected_status)
                    await quiet(page)
                    await page.reload()
                    await ready(page)
                    await expect(page.locator('[data-roadmap-item]').first).to_have_value(expected_status)
                    record['roadmap_smoke']['persisted'] = True

                assert record['docked']['workspace_reflowed'] and 400 <= record['docked']['width'] <= 480
                assert not record['docked']['old_thread_auto_opened']
                assert record['history']['all_project_scoped'] and record['history']['messages_restored'] and record['history']['new_conversation_clean']
                assert all(all(item.values()) for item in record['navigation'].values())
                assert record['presentation']['extra_provider_requests'] == 0
                assert record['roadmap_smoke']['persisted']
            if stage in ('setup', 'regulatory', 'roadmap', 'all', 'presentation'):
                # The six demo declarations are explicit; discard redundant machine
                # proposals through the same review controls available to the user.
                await nav(page, 'project')
                await page.locator('[data-tab="facts"]').click()
                await ready(page)
                if project['project_type'] != 'idea':
                    record['startup_idea_only_actions'] = await page.locator('[data-action="infer-facts"], [data-action="open-onboarding"]').count()
                    assert record['startup_idea_only_actions'] == 0
                while await page.locator('[data-action="reject-fact"]').count():
                    async with page.expect_response(lambda r:r.request.method=='DELETE' and '/facts/' in r.url):
                        await page.locator('[data-action="reject-fact"]').first.click()
                    await ready(page)
                await nav(page, 'roadmap')
                record['roadmap_action_available'] = await page.locator('[data-action="generate-roadmap"]').count() > 0
                assert record['roadmap_action_available']
                payload = None
                if stage not in ('roadmap', 'presentation'):
                    await nav(page, 'regulatory')
                    async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/assessments'), timeout=240_000) as response:
                        await page.locator('[data-action="generate-assessment"]').click()
                    res = await response.value
                    assert res.status==200
                    payload = await res.json()
                elif stage == 'presentation':
                    assessments=await page.evaluate('(id)=>window.RegBridgeEntrepreneurApi.assessments(id)',project['id'])
                    payload=next((item for item in reversed(assessments) if item['status']=='completed' and item.get('verification_verdict') in ('pass','pass_with_warnings') and any(item.get('result',{}).get(key) for key in ('obligations','recommendations'))),None)
                    if payload is not None:
                        await nav(page, 'regulatory')
                        await page.locator(f'[data-action="select-assessment"][data-version="{payload["version"]}"]').click()
                        await ready(page)
                        await expect(page.locator('[data-workspace]')).to_contain_text(f'Version {payload["version"]}')
                if payload is not None:
                    record['assessment'] = {k:payload.get(k) for k in ('id','version','status','verification_verdict')}
                    record['assessment']['result_keys'] = list(payload.get('result',{}))
                    record['assessment']['counts'] = {k:len(payload.get('result',{}).get(k,[])) for k in ('obligations','recommendations','uncertainties','sources')}
                    print(json.dumps({'assessment':record['assessment']},ensure_ascii=False),flush=True)
                await quiet(page)
                await page.reload()
                await ready(page)
                await nav(page, 'roadmap')
                async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/roadmaps'), timeout=30_000) as response:
                    await page.locator('[data-action="generate-roadmap"]').click()
                res=await response.value
                roadmap=await res.json()
                record['roadmap']={'http':res.status,'version':roadmap.get('version'),'items':len(roadmap.get('items',[])),'keys':list(roadmap)}
                assert res.status==200 and roadmap['items'], 'Roadmap missing'
                await quiet(page)
                await page.reload()
                await ready(page)
                await page.locator('details.roadmap-item').first.locator('summary').click()
                status=page.locator('[data-roadmap-item]').first
                async with page.expect_response(lambda r:r.request.method=='PATCH' and '/roadmaps/' in r.url):
                    await status.select_option('completed' if roadmap['items'][0]['status']=='in_progress' else 'in_progress')
                expected='completed' if roadmap['items'][0]['status']=='in_progress' else 'in_progress'
                await quiet(page)
                await ready(page)
                await page.reload()
                await ready(page)
                await expect(page.locator('[data-roadmap-item]').first).to_have_value(expected)
                record['roadmap']['status_persisted']=True
            if stage in ('copilot','all','presentation'):
                await page.locator('[data-open-copilot]').click()
                drawer=page.locator('[data-copilot-drawer]')
                record['drawer_width']=(await drawer.bounding_box())['width']
                await page.locator('[data-expand-copilot]').click()
                await expect(page.locator('body')).to_have_class(re.compile('copilot-fullscreen'))
                await page.wait_for_timeout(500)
                record['fullscreen_width']=(await drawer.bounding_box())['width']
                assert record['fullscreen_width']>=1438
                await page.screenshot(path=str(OUT/'demo-fullscreen-desktop.png'))
                await page.locator('[data-expand-copilot]').click()
                await page.locator('#copilot-question').fill('Quelles sont les principales obligations réglementaires pour EnerSight, et quelles informations manquent encore ?')
                async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/responses'), timeout=240_000) as response:
                    await page.locator('[data-submit-copilot]').click()
                    await expect(page.locator('[data-copilot-generating]')).to_be_visible()
                    await page.locator('[data-close-copilot]').click()
                    await nav(page,'roadmap')
                res=await response.value
                payload=await res.json()
                record['copilot']={'http':res.status,'answer_chars':len(payload.get('assistant_message',{}).get('content','')),'keys':list(payload),'orchestration_status':payload.get('orchestration_status'),'warnings':payload.get('warnings')}
                assert res.status==201 and record['copilot']['answer_chars']>0
                assert payload.get('orchestration_status') == 'succeeded', 'Copilot orchestration did not succeed'
                assert not payload.get('warnings'), 'Copilot did not return an accepted verified answer'
                await page.locator('[data-open-copilot]').click()
                await expect(page.locator('[data-copilot-generating]')).to_be_hidden()
                await expect(page.locator('[data-copilot-messages]')).to_contain_text(payload['assistant_message']['content'])
                await page.locator('[data-expand-copilot]').click()
                await page.set_viewport_size({'width':390,'height':844})
                await page.wait_for_timeout(500)
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert (await drawer.bounding_box())['width']>=389
                for selector in ('[data-expand-copilot]','[data-close-copilot]','[data-submit-copilot]'):
                    await expect(page.locator(selector)).to_be_in_viewport()
                await page.screenshot(path=str(OUT/'demo-fullscreen-mobile.png'))
                record['copilot']['response_requests']=sum(e['method']=='POST' and e['path'].endswith('/responses') for e in record['http'])
                assert record['copilot']['response_requests']==1
                record['copilot']['hidden_completion_preserved']=True
                await page.locator('[data-close-copilot]').click()
                await page.set_viewport_size({'width':1440,'height':1000})
            if stage in ('contracts','all','post','presentation'):
                await nav(page,'documents')
                docs=await page.evaluate('(id)=>window.RegBridgeEntrepreneurApi.projectDocuments(id)',project['id'])
                document=next((d for d in docs if d['title']=='Contrat EnerSight Demo'),None)
                if document is None:
                    await page.locator('[data-action="show-upload"]').click()
                    await page.locator('input[name="upload"]').set_input_files({'name':'enersight-demo.txt','mimeType':'text/plain','buffer':CONTRACT.encode('utf-8')})
                    await page.locator('input[name="title"]').fill('Contrat EnerSight Demo')
                    async with page.expect_response(lambda r:r.request.method=='POST' and '/documents?' in r.url, timeout=60_000) as response:
                        await page.locator('[data-action="submit-upload"]').click()
                    res=await response.value
                    record['upload_http']=res.status
                    assert res.status==201
                    uploaded=await res.json()
                    document=uploaded.get('document',uploaded)
                record['document_id']=document['id']
                for _ in range(30):
                    versions=await page.evaluate('(id)=>window.RegBridgeEntrepreneurApi.documentVersions(id)',document['id'])
                    if versions and versions[0]['extraction_status'] in ('ready','failed'):break
                    await page.wait_for_timeout(2000)
                version=versions[0]
                record['extraction']={k:version.get(k) for k in ('id','extraction_status','malware_scan_status','version_number')}
                assert version['extraction_status']=='ready' and version['malware_scan_status']=='clean'
                await nav(page,'contracts')
                await page.locator('[data-contract-document]').select_option(document['id']+'|'+version['id'])
                analyses=await page.evaluate('(id)=>window.RegBridgeEntrepreneurApi.documentAnalyses(id)',document['id'])
                payload=next((a for a in reversed(analyses) if a['status']=='completed'),None) if stage in ('post', 'presentation') else None
                if payload is None:
                    async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/analyses'),timeout=240_000) as response:
                        await page.locator('[data-action="analyze-contract"]').click()
                    res=await response.value
                    assert res.status==201
                    payload=await res.json()
                record['analysis']={k:payload.get(k) for k in ('id','status','provider','model','error_code')}
                record['analysis']['observations']=len(payload.get('observations',[]))
                assert payload['status']=='completed' and payload['observations']
                for item in payload['observations']:
                    assert item['document_version_id']==version['id']
                    assert CONTRACT[item['start_char']:item['end_char']]==item['source_quote']
                await quiet(page)
                await page.reload()
                await ready(page)
                await expect(page.locator('[data-workspace]')).to_contain_text(payload['observations'][0]['source_quote'])
            if stage in ('compliance','all','post','presentation'):
                if project['project_type']=='idea':
                    await nav(page,'project')
                    async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/transition')) as response:
                        await page.locator('[data-action="transition-project"]').click()
                    assert (await response.value).status==200
                    await ready(page)
                await nav(page,'compliance')
                frameworks=await page.evaluate('()=>window.RegBridgeEntrepreneurApi.frameworks()')
                framework=next(f for f in frameworks if f['name']=='Synthetic Test Framework')['versions'][0]
                record['framework']='Existing Synthetic Test Framework — demonstration only, not a regulatory certification'
                await page.locator('[data-compliance-framework]').select_option(framework['id'])
                await ready(page)
                async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/adoptions')) as response:
                    await page.locator('[data-action="adopt-framework"]').click()
                assert (await response.value).status==201
                await ready(page)
                control=page.locator('.control-card').first
                await expect(control).to_be_visible()
                await control.locator('[data-control-status]').select_option('IN_PROGRESS')
                await control.locator('[data-control-applicability]').select_option('APPLICABLE')
                async with page.expect_response(lambda r:r.request.method=='PATCH' and '/compliance/controls/' in r.url) as response:
                    await control.locator('[data-action="save-control"]').click()
                record['control_update_http']=(await response.value).status
                assert record['control_update_http']==200
                await ready(page)
                async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/scores')) as response:
                    await page.locator('[data-action="calculate-score"]').click()
                res=await response.value
                payload=await res.json()
                record['score']={k:payload.get(k) for k in ('id','score','numerator','denominator','method_version')}
                assert res.status==201 and payload['score'] is not None
                await expect(page.locator('.score-card')).to_contain_text(f"{payload['score']:g} %")
                await ready(page)
                await page.reload()
                await ready(page)
                await page.locator('[data-compliance-framework]').select_option(framework['id'])
                await ready(page)
                await expect(page.locator('.score-card')).to_contain_text(f"{payload['score']:g} %")
                record['score']['persisted']=True
            await quiet(page)
            if stage in ('all','post','presentation'):
                await page.locator('[data-logout]').click()
                await page.wait_for_url(re.compile(r'/auth/login/|:18080/'),timeout=30_000)
                record['logout']=True
                authenticated=False
            assert not record['page_errors'] and not record['failed_requests']
            assert not [item for item in record['http'] if item['status']>=400]
            record['passed']=True
        except Exception as exc:
            record['passed']=False
            record['failure_type']=type(exc).__name__
            record['failure_frames']=[f'{f.name}:{f.lineno}' for f in traceback.extract_tb(exc.__traceback__) if f.filename.endswith('demo_acceptance.py')]
            # Exception text may contain login secrets or callback URLs: never emit it.
            if authenticated:
                record['visible_workspace']=(await page.locator('[data-workspace]').inner_text())[:4000]
            print('Demo stage failed: '+type(exc).__name__,flush=True)
        finally:
            if authenticated:
                await page.screenshot(path=str(OUT/f'demo-{stage}.png'))
            (OUT/f'demo-{stage}.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in record.items() if k not in ('visible_workspace','http')},ensure_ascii=False),flush=True)
            await browser.close()
    return record['passed']


if __name__=='__main__':
    raise SystemExit(0 if asyncio.run(run(sys.argv[1] if len(sys.argv)>1 else 'setup')) else 1)
