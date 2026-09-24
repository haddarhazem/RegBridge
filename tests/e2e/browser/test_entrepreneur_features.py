"""Product UX with real local OIDC/project persistence and controlled AI latency."""
import asyncio
import os
import re
import uuid

import pytest
from playwright.async_api import expect

from .conftest import authenticate, complete_onboarding, create_project

pytestmark = pytest.mark.browser_e2e


async def test_launch_roadmap_without_regulatory_assessment(browser_page, synthetic_user):
    """A real browser/API/DB journey proves that regulatory analysis is optional."""
    page = browser_page
    errors = []
    failed_responses = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', lambda response: failed_responses.append((response.status, response.url)) if response.status >= 400 else None)
    await authenticate(page, synthetic_user)
    await create_project(page, 'Plateforme SaaS B2B EnergyTech avec IA, IoT et données personnelles en France.')
    await page.wait_for_url(re.compile(r"view=onboarding"), timeout=10_000)
    await complete_onboarding(page, {
        'activity': 'Plateforme SaaS B2B d’analyse énergétique pour les PME',
        'sector': 'EnergyTech',
        'technology': 'Intelligence artificielle, machine learning, IoT et cloud',
        'data': 'Données personnelles clients et données techniques énergétiques',
        'market': 'PME B2B en France',
        'location': 'France',
    })
    await page.locator('[data-nav-view="roadmap"]').first.click()
    await expect(page.locator('[data-action="generate-roadmap"]')).to_be_visible()
    await expect(page.locator('[data-workspace]')).to_contain_text('Couverture réglementaire à compléter')
    async with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/roadmaps')) as response_info:
        await page.locator('[data-action="generate-roadmap"]').click()
    response = await response_info.value
    assert response.status == 200
    payload = await response.json()
    assert payload['regulatory_assessment_id'] is None
    assert payload['regulatory_coverage'] == 'incomplete'
    assert len(payload['items']) == 14
    await expect(page.locator('.roadmap-item')).to_have_count(14)
    for heading in ('Préparer la structure', 'Préparer l’exploitation', 'Données et numérique', 'Avant le lancement'):
        await expect(page.locator('[data-workspace]')).to_contain_text(heading)
    for expected in ('Données personnelles', 'Sécurité et hébergement', 'Selon votre projet', 'Général'):
        await expect(page.locator('[data-workspace]')).to_contain_text(expected)
    assert 'Équipe et RH' not in await page.locator('[data-workspace]').inner_text()
    await page.screenshot(path='artifacts/browser-e2e/launch-roadmap-baseline.png', full_page=True, animations='disabled')
    await page.locator('.roadmap-item summary').first.click()
    await page.locator('[data-roadmap-item]').first.select_option('in_progress')
    await page.reload()
    await expect(page.locator('[data-roadmap-item]').first).to_have_value('in_progress')
    await page.locator('[data-nav-view="regulatory"]').click()
    await expect(page.locator('[data-workspace]')).to_contain_text('Aucune évaluation')
    await page.locator('[data-nav-view="roadmap"]').first.click()
    await expect(page.locator('.roadmap-item')).to_have_count(14)
    assert not errors
    assert not failed_responses


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
    from app.modules.documents.contract_analysis_models import ContractAnalysis, ContractClause

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
            project.activity='Plateforme SaaS'
            project.sector='Services numériques'
            project.technology='Application web'
            project.confirmed_fields={'activity':'confirmed','sector':'confirmed','technology':'confirmed'}
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
            analysis=ContractAnalysis(project_id=project_id,document_version_id=version.id,analysis_version=1,overall_risk_level='medium',summary='Synthetic contract analysis.',recommendations=['Review the source evidence.'],missing_context=[],verification_status='completed')
            session.add(analysis)
            await session.flush()
            session.add(ContractClause(contract_analysis_id=analysis.id,clause_order=1,clause_type='duration',heading='Duration',extracted_text=quote,risk_level='medium',finding='Synthetic extraction',recommendation='Review the duration.',source_refs={'evidence':[{'document_version_id':str(version.id),'quote':quote,'start_char':0,'end_char':len(quote),'locator':'Synthetic source'}],'analysis':{'title':'Duration','status':'AMBIGUOUS','plain_language_summary':'Synthetic explanation.','purpose':'Synthetic purpose.','issues':['Synthetic extraction'],'limitations':[]}}))
            await session.commit()
        await page.goto(f'/entrepreneur/?view=regulatory&project={project_id}')
        await expect(page.locator('[data-workspace]')).to_contain_text('Synthetic assessment version 2')
        await expect(page.locator('[data-workspace]')).to_contain_text('Synthetic coverage limitation')
        await expect(page.locator('[data-workspace]')).to_contain_text('Synthetic authority')
        await page.locator('[data-action="select-assessment"][data-version="1"]').click()
        await expect(page.locator('[data-workspace]')).to_contain_text('Synthetic assessment version 1')
        await page.locator('[data-nav-view="roadmap"]').first.click()
        await page.locator('[data-action="generate-roadmap"]').click()
        await expect(page.locator('.roadmap-item')).to_have_count(11)
        await expect(page.locator('[data-workspace]')).to_contain_text('Préparer la structure')
        await expect(page.locator('[data-workspace]')).to_contain_text('Évaluation réglementaire')
        await page.locator('.roadmap-item summary').first.click()
        await page.locator('[data-roadmap-item]').first.select_option('completed')
        await expect(page.locator('.roadmap-progress')).to_contain_text('1 / 11')
        await page.reload()
        await expect(page.locator('.roadmap-progress')).to_contain_text('1 / 11')
        await page.locator('[data-action="generate-roadmap"]').click()
        await expect(page.locator('[data-action="select-roadmap"]')).to_have_count(2)
        await page.locator('[data-action="select-roadmap"][data-version="1"]').click()
        await expect(page.locator('.roadmap-progress')).to_contain_text('1 / 11')
        await page.locator('[data-nav-view="contracts"]').click()
        await expect(page.locator('.contract-analysis')).to_contain_text(quote)
        await expect(page.locator('.contract-analysis')).to_contain_text('VERSION 1')
        await expect(page.locator('.contract-analysis')).not_to_contain_text(str(version.id))
        await page.locator('.contract-clause-detail summary').click()
        await expect(page.locator('.contract-clause-detail')).to_contain_text('Synthetic explanation.')
        await expect(page.locator('.contract-clause-detail')).to_contain_text('Review the duration.')
        await page.locator('[data-action="copilot-analysis"]').click()
        await expect(page.locator('[data-copilot-drawer]')).to_have_attribute('aria-hidden', 'false')
        await page.locator('#copilot-question').fill('Quels sont les principaux risques de ce contrat ?')
        await page.locator('[data-submit-copilot]').click()
        await expect(page.locator('[data-copilot-messages]')).to_contain_text('Synthetic extraction', timeout=30_000)
        await page.screenshot(path='artifacts/browser-e2e/features-contracts.png')
        assert not errors
    finally:
        await engine.dispose()


def _synthetic_contract_pdf() -> bytes:
    """Build an in-memory, text-based PDF for the real extraction path."""

    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    contract = """PARTIES
Entre EnerSight SAS ci-apres le Prestataire, et Client SA ci-apres le Client.

OBJET
Le Prestataire fournit une plateforme SaaS de suivi energetique.

PERIMETRE
La prestation couvre la plateforme et son support standard.

PAIEMENT
Le Client regle les factures selon les modalites convenues entre les parties.

DUREE
Le contrat est conclu pour 12 mois. Il prend automatiquement fin apres 24 mois.

CONFIDENTIALITE
Le Client garde confidentielles les informations du Prestataire.

PROPRIETE INTELLECTUELLE
La propriete intellectuelle des livrables sera definie ulterieurement.

RESPONSABILITE
La responsabilite du Prestataire est illimitee.

DONNEES PERSONNELLES
Les parties traitent des donnees personnelles des utilisateurs.

DROIT APPLICABLE
Le present contrat est soumis au droit francais."""
    for line in contract.splitlines():
        if line:
            pdf.multi_cell(180, 7, line)
        else:
            pdf.ln(7)
    rendered = pdf.output()
    return bytes(rendered) if isinstance(rendered, (bytes, bytearray)) else rendered.encode("latin-1")


@pytest.mark.skipif(
    os.getenv("CONTRACT_EXTERNAL_SEMANTIC_ANALYSIS_E2E") != "1",
    reason="requires an explicitly authorized external semantic contract provider",
)
async def test_contract_upload_analysis_and_contract_agent_real_browser(browser_page, synthetic_user):
    """A real local browser creates, persists, reads, and questions a PDF analysis."""

    page = browser_page
    errors: list[str] = []
    response_failures: list[tuple[int, str]] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: response_failures.append((response.status, response.url)) if response.status >= 500 else None)

    await authenticate(page, synthetic_user)
    await create_project(page, "Synthetic Energy SaaS project used only for contract browser acceptance.")
    await page.locator('[data-nav-view="documents"]').click()
    await expect(page.locator('[data-workspace]')).to_contain_text("DOCUMENTS")
    await page.get_by_role("button", name=re.compile("Importer un document", re.IGNORECASE)).click()
    await page.locator("form[data-form='upload-document'] input[type='file']").set_input_files({
        "name": "synthetic-contract.pdf",
        "mimeType": "application/pdf",
        "buffer": _synthetic_contract_pdf(),
    })
    await page.locator("form[data-form='upload-document'] input[name='title']").fill("Synthetic browser contract")
    async with page.expect_response(lambda response: response.request.method == "POST" and "/documents?" in response.url) as upload_info:
        await page.locator("button[data-action='submit-upload']").click()
    upload_response = await upload_info.value
    assert upload_response.status == 201
    upload_payload = await upload_response.json()
    document_id = upload_payload["document"]["id"]
    version_id = upload_payload["version"]["id"]

    document_row = page.locator(".document-list .document-row").filter(has_text="Synthetic browser contract")
    await expect(document_row).to_be_visible(timeout=30_000)
    await document_row.locator('[data-action="open-document"]').click()
    analyze_button = page.get_by_role("button", name=re.compile("Analyser le contrat", re.IGNORECASE))
    await expect(analyze_button).to_be_visible(timeout=60_000)
    await expect(page.locator(".document-detail")).to_contain_text("Document pr")

    async with page.expect_response(
        lambda response: response.request.method == "POST" and response.url.endswith(f"/documents/{document_id}/versions/{version_id}/analyses")
    ) as analysis_info:
        await analyze_button.click()
    analysis_response = await analysis_info.value
    assert analysis_response.status == 201
    analysis_payload = await analysis_response.json()
    assert analysis_payload["document_id"] == document_id
    assert analysis_payload["document_version_id"] == version_id
    assert analysis_payload["status"] == "completed"
    assert analysis_payload["risk_index"]["contributors"]

    await expect(page.locator(".contract-analysis")).to_be_visible(timeout=30_000)
    await expect(page.locator(".contract-risk-index")).to_contain_text("Contributeurs")
    await expect(page.locator(".contract-risk-index")).to_contain_text("Formule")
    await expect(page.locator('[data-contract-clause]')).to_have_count(len(analysis_payload["clauses"]))

    first_clause = page.locator("[data-contract-clause]").first
    await first_clause.locator("summary").click()
    await expect(first_clause).to_contain_text("Texte original")

    recommended_clause = next(clause for clause in analysis_payload["clauses"] if clause["recommendation"])
    recommended_detail = page.locator(f'#contract-clause-{recommended_clause["id"]}')
    await recommended_detail.locator("summary").click()
    await expect(recommended_detail).to_contain_text("Recommandation")

    liability_clause = next(clause for clause in analysis_payload["clauses"] if clause["clause_type"] == "liability")
    liability = page.locator(f'#contract-clause-{liability_clause["id"]}')
    await liability.locator("summary").click()
    await expect(liability).to_contain_text("Pourquoi")
    await expect(liability).to_contain_text("responsabilit")

    missing_termination = page.locator('[data-contract-clause][data-clause-status="MISSING"]').filter(has_text=re.compile("siliation", re.IGNORECASE))
    await expect(missing_termination).to_have_count(1)
    await missing_termination.locator("summary").click()
    await expect(missing_termination).to_contain_text("Aucun passage source")

    contradiction = page.locator('[data-contract-clause][data-clause-status="CONTRADICTORY"]')
    await expect(contradiction).to_have_count(1)
    await contradiction.locator("summary").click()
    await expect(contradiction).to_contain_text("12 mois")
    await expect(contradiction).to_contain_text("24 mois")

    await page.locator('[data-action="copilot-analysis"]').click()
    await expect(page.locator('[data-copilot-drawer]')).to_have_attribute("aria-hidden", "false")

    async def ask_contract(question: str) -> str:
        await page.locator("#copilot-question").fill(question)
        async with page.expect_response(lambda response: response.request.method == "POST" and "/responses" in response.url, timeout=120_000) as response_info:
            await page.locator("[data-submit-copilot]").click()
        response = await response_info.value
        assert response.status < 500
        payload = await response.json()
        await expect(page.locator("[data-copilot-messages]")).to_contain_text(question, timeout=30_000)
        return payload["assistant_message"]["content"]

    risks = await ask_contract("Quels sont les principaux risques de ce contrat ?")
    termination = await ask_contract("Y a-t-il une clause de resiliation ?")
    intellectual_property = await ask_contract("Que prevoit le contrat concernant la propriete intellectuelle ?")
    non_compete = await ask_contract("Le contrat contient-il une clause de non-concurrence ?")
    penalty = await ask_contract("Quelle penalite est prevue en cas de retard de paiement ?")
    assert "principaux points" in risks
    assert "identifi" in termination
    assert "titulaire" in intellectual_property.casefold()
    assert "identifi" in non_compete
    assert "inventer" in penalty

    await page.locator('[data-nav-view="documents"]').click()
    await expect(page.locator(".document-summary")).to_contain_text("ANALYSES DE CONTRATS")
    await expect(page.locator(".document-summary")).to_contain_text("1")
    assert not errors
    assert not response_failures
