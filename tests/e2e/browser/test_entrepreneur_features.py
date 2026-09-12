"""Product UX with real local OIDC/project persistence and controlled AI latency."""
import asyncio
import re
import uuid

import pytest
from playwright.async_api import expect

from .conftest import authenticate, create_project

pytestmark = pytest.mark.browser_e2e


async def test_copilot_visibility_fullscreen_and_hidden_completion(browser_page, synthetic_user):
    page = browser_page
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    await authenticate(page, synthetic_user)
    await create_project(page)
    pending, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = []

    async def delayed_response(route):
        calls.append(route.request.url)
        pending.set()
        await asyncio.wait_for(release.wait(), 40)
        await route.fulfill(status=201, json={
            'user_message': {'id': 'synthetic-user-message', 'role': 'user', 'content': 'Synthetic active question'},
            'assistant_message': {'id': 'synthetic-answer', 'role': 'assistant', 'content': 'Synthetic completed response'},
        })
        finished.set()

    await page.route('**/conversations/*/responses', delayed_response)
    await page.locator('[data-open-copilot]').click()
    await page.locator('#copilot-question').fill('Synthetic active question')
    await page.locator('[data-submit-copilot]').click()
    await asyncio.wait_for(pending.wait(), 20)
    try:
        await page.locator('[data-expand-copilot]').click()
        await expect(page.locator('body')).to_have_class(re.compile('copilot-fullscreen'))
        await page.locator('#copilot-question').fill('Unsent synthetic draft')
        await page.locator('[data-close-copilot]').click()
        await expect(page.locator('[data-copilot-drawer]')).to_have_attribute('aria-hidden', 'true')
        await expect(page.locator('[data-open-copilot]')).to_be_focused()
        await page.locator('[data-nav-view="roadmap"]').first.click()
        await expect(page.locator('[data-workspace]')).to_contain_text('Roadmap non générée')
        await page.locator('[data-open-copilot]').click()
        await expect(page.locator('[data-copilot-generating]')).to_be_visible()
        await expect(page.locator('[data-copilot-messages]')).to_contain_text('Synthetic active question')
        await expect(page.locator('#copilot-question')).to_have_value('Unsent synthetic draft')
        await page.keyboard.press('Escape')
        await expect(page.locator('[data-expand-copilot]')).to_have_attribute('aria-pressed', 'false')
        await page.keyboard.press('Escape')
        for view in ('regulatory', 'contracts'):
            await page.locator(f'[data-nav-view="{view}"]').click()
            await expect(page.locator('[data-workspace] .inline-error')).to_have_count(0)
        release.set()
        await asyncio.wait_for(finished.wait(), 10)
        await expect(page.locator('[data-open-copilot]')).to_have_attribute('aria-label', 'Copilote : réponse disponible')
        await expect(page.locator('[data-copilot-drawer]')).to_have_attribute('aria-hidden', 'true')
        await page.locator('[data-open-copilot]').click()
        await expect(page.locator('[data-copilot-messages]')).to_contain_text('Synthetic completed response')
        await expect(page.locator('[data-copilot-generating]')).to_be_hidden()
        await expect(page.locator('#copilot-question')).to_have_value('Unsent synthetic draft')
        await page.locator('[data-expand-copilot]').click()
        await page.screenshot(path='artifacts/browser-e2e/features-fullscreen-desktop.png', animations='disabled')
        await page.set_viewport_size({'width':390, 'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        for selector in ('[data-expand-copilot]', '[data-close-copilot]', '[data-submit-copilot]'):
            await expect(page.locator(selector)).to_be_visible()
        await page.screenshot(path='artifacts/browser-e2e/features-fullscreen-mobile.png', animations='disabled')
        assert len(calls) == 1
        assert not errors
    finally:
        release.set()


async def test_versioned_assessment_roadmap_and_contract_reading(browser_page, synthetic_user):
    """Seed synthetic results only; roadmap generation/update and all reads are real HTTP/DB."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.config import get_settings
    from app.modules.projects.models import Project
    from app.modules.regulatory.assessment_models import AssessmentInputSnapshot, RegulatoryAssessment
    from app.modules.documents.models import Document, DocumentVersion
    from app.modules.documents.contract_analysis_models import ContractAnalysis, ContractFinding

    page=browser_page
    errors=[]
    page.on('pageerror', lambda error: errors.append(str(error)))
    await authenticate(page, synthetic_user)
    await create_project(page)
    project_id=uuid.UUID(await page.evaluate('async () => (await window.RegBridgeEntrepreneurApi.projects())[0].id'))
    engine=create_async_engine(get_settings().database_url)
    try:
        async with async_sessionmaker(engine,expire_on_commit=False)() as session:
            project=await session.get(Project,project_id)
            snapshot=AssessmentInputSnapshot(project_id=project_id,facts=[],snapshot_hash='f'*64)
            session.add(snapshot)
            await session.flush()
            for number in (1,2):
                session.add(RegulatoryAssessment(project_id=project_id,snapshot_id=snapshot.id,version=number,status='completed',verification_verdict='pass',source_provenance=[{'point_id':'synthetic-point','organization':'Synthetic authority'}],result={'answer':f'Synthetic assessment version {number}','obligations':[],'recommendations':[{'conclusion_id':'synthetic-conclusion','statement':'Synthetic preparation step','category':'recommendation','source_refs':['synthetic-point']}],'uncertainties':[{'conclusion_id':'missing','statement':'Synthetic coverage limitation','category':'uncertainty','source_refs':[]}],'sources':['Synthetic authority']}))
            document=Document(owner_user_id=project.owner_user_id,project_id=project_id,title='Synthetic versioned contract',document_type='txt',classification='confidential',visibility='private',processing_status='uploaded')
            session.add(document)
            await session.flush()
            quote='Synthetic contract excerpt for UI validation only.'
            version=DocumentVersion(document_id=document.id,version_number=1,original_filename='synthetic.txt',storage_key=f'ui-fixture/{uuid.uuid4()}',mime_type='text/plain',size_bytes=len(quote),sha256='a'*64,malware_scan_status='clean',extracted_text=quote,uploaded_by_user_id=project.owner_user_id)
            session.add(version)
            await session.flush()
            document.current_version_id=version.id
            analysis=ContractAnalysis(project_id=project_id,document_id=document.id,document_version_id=version.id,strategy='v2_structured_evidence',prompt_version='synthetic-ui-fixture',status='completed',created_by_user_id=project.owner_user_id)
            session.add(analysis)
            await session.flush()
            session.add(ContractFinding(analysis_id=analysis.id,finding_index=0,finding_type='FINDING',category='duration',statement='Synthetic extraction',evidence_document_version_id=version.id,evidence_quote=quote,evidence_start_char=0,evidence_end_char=len(quote)))
            await session.commit()
        await page.goto(f'/entrepreneur/?view=regulatory&project={project_id}')
        await expect(page.locator('[data-workspace]')).to_contain_text('Synthetic assessment version 2')
        await expect(page.locator('[data-workspace]')).to_contain_text('Synthetic coverage limitation')
        await expect(page.locator('[data-workspace]')).to_contain_text('Synthetic authority')
        await page.locator('[data-action="select-assessment"][data-version="1"]').click()
        await expect(page.locator('[data-workspace]')).to_contain_text('Synthetic assessment version 1')
        await page.locator('[data-nav-view="roadmap"]').first.click()
        await page.locator('[data-action="generate-roadmap"]').click()
        await expect(page.locator('.roadmap-item')).to_have_count(2)
        await page.locator('.roadmap-item summary').first.click()
        await page.locator('[data-roadmap-item]').first.select_option('completed')
        await expect(page.locator('.roadmap-progress')).to_contain_text('1 / 2')
        await page.reload()
        await expect(page.locator('.roadmap-progress')).to_contain_text('1 / 2')
        await page.locator('[data-action="generate-roadmap"]').click()
        await expect(page.locator('[data-action="select-roadmap"]')).to_have_count(2)
        await page.locator('[data-action="select-roadmap"][data-version="1"]').click()
        await expect(page.locator('.roadmap-progress')).to_contain_text('1 / 2')
        await page.locator('[data-nav-view="contracts"]').click()
        await expect(page.locator('.analysis-card')).to_contain_text(quote)
        await expect(page.locator('.analysis-card')).to_contain_text('v1')
        await expect(page.locator('.analysis-card')).not_to_contain_text(str(version.id))
        await page.screenshot(path='artifacts/browser-e2e/features-contracts.png')
        assert not errors
    finally:
        await engine.dispose()
