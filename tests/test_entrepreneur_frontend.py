from pathlib import Path

import httpx
import pytest

from app.main import app


ROOT = Path(__file__).parents[1] / "frontend"
ENTREPRENEUR = ROOT / "entrepreneur"


@pytest.mark.asyncio
async def test_entrepreneur_route_serves_authenticated_productivity_shell() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/entrepreneur/")

    assert response.status_code == 200
    html = response.text
    assert html.count("<main") == 1
    assert 'class="app-sidebar"' in html
    assert 'class="app-topbar"' in html
    assert 'class="copilot-bar"' in html
    assert 'data-workspace' in html
    assert 'data-logout' in html
    assert "oidc-client-ts.min.js" in html


def test_entrepreneur_api_adapter_uses_only_real_backend_contracts() -> None:
    adapter = (ENTREPRENEUR / "api.js").read_text(encoding="utf-8")
    app_script = (ENTREPRENEUR / "app.js").read_text(encoding="utf-8")
    views = (ENTREPRENEUR / "views.js").read_text(encoding="utf-8")

    expected_paths = (
        "/projects/${projectId}",
        "/projects/${projectId}/onboarding",
        "/projects/${projectId}/facts",
        "/projects/${projectId}/assessments",
        "/projects/${projectId}/roadmaps",
        "/projects/${projectId}/documents",
        "/documents/${documentId}/analyses",
        "/projects/${projectId}/members",
        "/projects/${projectId}/compliance/controls",
    )
    for path in expected_paths:
        assert path in adapter
    assert "fetch(" not in app_script + views
    assert "apiRequest" in adapter
    assert "Authorization" not in adapter + app_script + views
    assert "access_token" not in adapter + app_script + views
    assert "console.log" not in adapter + app_script + views


def test_projects_are_discovered_from_server_and_documents_fail_closed() -> None:
    store = (ENTREPRENEUR / "store.js").read_text(encoding="utf-8")
    views = (ENTREPRENEUR / "views.js").read_text(encoding="utf-8")
    app_script = (ENTREPRENEUR / "app.js").read_text(encoding="utf-8")

    assert "userId" in store
    assert "active-project" in store
    assert "documentIds" not in store
    assert "rememberDocument" not in store
    assert "api.projects()" in app_script
    assert "projectIds" not in store
    assert "rememberProject" not in store
    assert "api.projectDocuments(projectId)" in app_script
    assert "Vos droits d’accès sont vérifiés à chaque ouverture" in views
    assert "Cette vue affiche les documents importés depuis ce navigateur" not in views
    assert "data-document-classification" in views
    for fake_metric in ("72% compliant", "8 documents complete", "4 regulations"):
        assert fake_metric not in views


def test_entrepreneur_navigation_is_role_and_lifecycle_aware() -> None:
    app_script = (ENTREPRENEUR / "app.js").read_text(encoding="utf-8")
    auth_runtime = (ROOT / "auth" / "auth-runtime.js").read_text(encoding="utf-8")
    auth_ui = (ROOT / "auth" / "auth.js").read_text(encoding="utf-8")

    assert "state.user.roles.includes('entrepreneur')" in app_script
    assert "/auth/login/?returnTo=" in app_script
    assert "state.project.project_type !== 'idea'" in app_script
    assert "['compliance', 'Conformité']" in app_script
    assert "Investisseurs" not in app_script
    assert "Veille réglementaire" not in app_script
    assert "'/entrepreneur/'" in auth_runtime
    assert "workspaceDestination" in auth_runtime + auth_ui


def test_views_cover_real_project_workflow_and_safety_copy() -> None:
    views = (ENTREPRENEUR / "views.js").read_text(encoding="utf-8")
    api = (ENTREPRENEUR / "api.js").read_text(encoding="utf-8")

    for behavior in (
        "createProject", "onboarding", "factsSection", "regulatory", "roadmap",
        "documents", "contracts", "access", "compliance",
    ):
        assert f"function {behavior}" in views
    assert "Déclaré par vous" in views
    assert "Déduit à partir de vos réponses" in views
    assert "Obligations" in views and "Recommandations" in views and "Incertitudes" in views
    assert "Ce score n’est pas une certification officielle" in views
    assert "ne remplace pas une validation juridique professionnelle" in views
    assert "Aucun changement automatique n’est appliqué" in views
    assert "uploadDocumentVersion" in api
    assert "analyzeContract" in api
    assert "retryDocumentExtraction" in api
    assert "extraction_status" in api + views
    assert "retry-extraction" in views
    assert "<dt>Identifiant</dt>" not in views


def test_compliance_frontend_uses_versioned_backend_contracts_and_server_score() -> None:
    adapter = (ENTREPRENEUR / "api.js").read_text(encoding="utf-8")
    app_script = (ENTREPRENEUR / "app.js").read_text(encoding="utf-8")
    views = (ENTREPRENEUR / "views.js").read_text(encoding="utf-8")

    for behavior in (
        "frameworks", "adoptFramework", "updateControl", "controlEvidence",
        "attachEvidence", "revokeEvidence", "calculateScore", "scoreHistory",
    ):
        assert behavior in adapter
    assert "/compliance/frameworks" in adapter
    assert "/projects/${projectId}/compliance/adoptions" in adapter
    assert "/projects/${projectId}/compliance/evidence/${evidenceId}/revoke" in adapter
    assert "state.selectedControlEvidence" in app_script
    assert "project_type !== 'idea'" in app_script
    assert "malware_scan_status === 'clean'" in views
    assert "extraction_status === 'ready'" in views
    assert "source_references" in views
    assert "scoreExplanation" not in views
    assert "score * 100" not in views
    assert "certification officielle" in views


def test_profile_uses_real_identity_roles_workspace_and_project_state() -> None:
    views = (ENTREPRENEUR / "views.js").read_text(encoding="utf-8")
    app_script = (ENTREPRENEUR / "app.js").read_text(encoding="utf-8")

    assert "Votre espace RegBridge." in views
    assert "Gérez votre identité, vos rôles et les espaces auxquels vous avez accès." in views
    assert "IDENTITÉ" in views
    assert "user.email" in views
    assert "RÔLES REGBRIDGE" in views
    assert "ESPACE ACTIF" in views
    assert "VOTRE PARCOURS" in views
    assert "Votre premier projet commence ici." in views
    assert "next.title" in views
    assert "ACCÈS AU COMPTE" in views
    assert "profile-logout" in views and "profile-logout" in app_script
    assert "user.roles.length > 1" in views
    assert "views.profile(state)" in app_script
    assert "<dt>Identifiant</dt>" not in views


def test_create_project_is_guided_accessible_and_keeps_real_payload() -> None:
    views = (ENTREPRENEUR / "views.js").read_text(encoding="utf-8")
    app_script = (ENTREPRENEUR / "app.js").read_text(encoding="utf-8")

    assert "Parlez-nous de votre projet." in views
    assert "Décrire" in views and "Préciser" in views and "Vérifier" in views
    assert 'placeholder="Ex. EcoTrack"' in views
    assert 'aria-describedby="project-name-help"' in views
    assert 'aria-describedby="project-description-help project-guidance"' in views
    assert "Ce que nous chercherons à comprendre" in views
    for field in ("Activité", "Secteur", "Technologie", "Données", "Marché", "Localisation"):
        assert field in views
    assert "RegBridge collecte uniquement les informations utiles" in views
    assert "Vous pourrez interrompre le parcours et le reprendre plus tard." in views
    assert "Créer le projet et continuer" in views
    assert "Projet créé." in app_script
    assert "raw_description: data.get('raw_description').trim()" in app_script


def test_empty_dashboard_and_copilot_copy_are_conditional() -> None:
    html = (ENTREPRENEUR / "index.html").read_text(encoding="utf-8")
    views = (ENTREPRENEUR / "views.js").read_text(encoding="utf-8")
    app_script = (ENTREPRENEUR / "app.js").read_text(encoding="utf-8")

    assert "Transformez votre idée en parcours concret." in views
    assert "Créer mon premier projet" in views
    assert "Décrivez votre activité" in views
    assert "Vérifiez les informations clés" in views
    assert "Construisez votre roadmap" in views
    assert "Créez ou sélectionnez un projet pour activer le contexte du copilote." in html + app_script
    assert "Le copilote utilise uniquement les informations autorisées du projet actif." in app_script
    assert "copilotButton.disabled = !state.project" in app_script


def test_copilot_uses_persisted_backend_conversation_and_authorized_project_identifier() -> None:
    html = (ENTREPRENEUR / "index.html").read_text(encoding="utf-8")
    api = (ENTREPRENEUR / "api.js").read_text(encoding="utf-8")
    app_script = (ENTREPRENEUR / "app.js").read_text(encoding="utf-8")

    assert "createConversation" in api
    assert "subject_type: 'project'" in api
    assert "subject_id: projectId" in api
    assert "/conversations/${conversationId}/responses" in api
    assert "api.conversation(conversation.id)" in app_script
    assert "api.askCopilot" in app_script
    assert "AbortController" in app_script
    assert "state.copilot.messages" in app_script
    assert "content_json?.sources" in app_script
    assert "state.roadmap ? ['Quelles sont mes prochaines étapes ?']" in app_script
    assert "Projet actif modifié. Une nouvelle conversation a été ouverte." in app_script
    assert 'role="dialog"' in html
    assert 'aria-live="polite"' in html
    assert "RegBridge analyse le contexte autorisé" in html
    assert "api.mistral" not in api.lower() + app_script.lower()
    assert "openai" not in api.lower() + app_script.lower()


def test_facts_and_assessment_enforce_real_confirmation_gate() -> None:
    views = (ENTREPRENEUR / "views.js").read_text(encoding="utf-8")
    app_script = (ENTREPRENEUR / "app.js").read_text(encoding="utf-8")

    assert "fact-editor" in views
    assert "window.prompt" not in app_script
    assert "api.correctFact" in app_script
    assert "api.confirmFact" in app_script
    assert "api.rejectFact" in app_script
    assert "pending_confirmation" in app_script + views
    assert "Certaines informations doivent encore être vérifiées." in app_script + views
    assert "Analyse basée sur un instantané immuable des informations confirmées" in views
    assert "await api.inferFacts(state.project.id)" in app_script


def test_ordinary_entrepreneur_copy_has_no_implementation_vocabulary() -> None:
    html = (ENTREPRENEUR / "index.html").read_text(encoding="utf-8")
    visible_html = "\n".join(line for line in html.splitlines() if "<script " not in line)
    visible_sources = "\n".join([
        visible_html,
        (ENTREPRENEUR / "views.js").read_text(encoding="utf-8"),
    ]).lower()

    for term in ("backend", "oidc", "jwt", "jwks", "provider_subject", "pkce", "sql", "database", "api endpoint"):
        assert term not in visible_sources


def test_entrepreneur_shell_is_responsive_accessible_and_reduced_motion_safe() -> None:
    html = (ENTREPRENEUR / "index.html").read_text(encoding="utf-8")
    css = (ENTREPRENEUR / "entrepreneur.css").read_text(encoding="utf-8")

    assert '<html lang="fr">' in html
    assert 'href="#workspace"' in html
    assert 'aria-label="Navigation entrepreneur"' in html
    assert 'aria-hidden="true"' in html
    assert 'aria-live="polite"' in html
    assert "@media (max-width: 820px)" in css
    assert "@media (max-width: 600px)" in css
    assert "prefers-reduced-motion: reduce" in css
    assert ".entrepreneur-app :focus-visible" in css
    assert "overflow-x" not in css or "overflow: hidden" in css
    assert ".profile-grid" in css
    assert "grid-template-columns: repeat(12" in css
    assert ".create-project-grid" in css
    assert ".step-list.create-steps" in css


def test_formdata_upload_does_not_force_json_content_type() -> None:
    runtime = (ROOT / "auth" / "auth-runtime.js").read_text(encoding="utf-8")

    assert "!(options.body instanceof FormData)" in runtime
    assert "apiRequest," in runtime
