from pathlib import Path

import httpx
import pytest

from app.main import app


ROOT = Path(__file__).parents[1] / "frontend"
INVESTOR = ROOT / "investor"


@pytest.mark.asyncio
async def test_investor_workspace_route_is_served() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/investor/")

    assert response.status_code == 200
    html = response.text
    assert '<html lang="fr">' in html
    assert 'class="investor-sidebar"' in html
    assert 'class="investor-topbar"' in html
    assert 'data-investor-workspace' in html
    assert "oidc-client-ts.min.js" in html


@pytest.mark.asyncio
async def test_investor_owner_list_alias_routes_are_served() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        matches = await client.get("/investor/matches/")
        briefs = await client.get("/investor/briefs/")

    assert matches.status_code == 200 and "view=matches" in matches.text
    assert briefs.status_code == 200 and "view=briefs" in briefs.text


def test_investor_frontend_uses_real_contracts_and_central_auth_client() -> None:
    api = (INVESTOR / "api.js").read_text(encoding="utf-8")
    script = (INVESTOR / "app.js").read_text(encoding="utf-8")
    runtime = (ROOT / "auth" / "auth-runtime.js").read_text(encoding="utf-8")

    for path in (
        "/investor/profile",
        "/investor/profile/versions",
        "/startups/search",
        "/investment-matches",
        "/investor/matches",
        "/investment-briefs",
        "/investor/briefs",
        "/investment-opportunities",
        "/events",
        "/contact-requests",
    ):
        assert path in api
    assert "apiRequest" in api
    assert "Authorization" not in api + script
    assert "access_token" not in api + script
    assert "localStorage" not in api + script
    assert "role === 'investor'" in runtime
    assert "return '/investor/'" in runtime
    assert "Authorization" not in api + script


def test_investor_frontend_exposes_the_approved_workspace_sections() -> None:
    html = (INVESTOR / "index.html").read_text(encoding="utf-8")
    script = (INVESTOR / "app.js").read_text(encoding="utf-8")
    api = (INVESTOR / "api.js").read_text(encoding="utf-8")
    styles = (INVESTOR / "investor.css").read_text(encoding="utf-8")

    for section in ("Essentiel", "Analyse", "Écosystème", "Système"):
        assert section in html
    for view in ("discovery", "detail", "match", "brief", "opportunities", "events", "connections", "profile"):
        assert f"state.view === '{view}'" in script or f"data-nav-view=\"{view}\"" in html
    assert "Informations insuffisantes" in script
    assert "investor-match-unknown" in styles
    assert script.count("<section>") >= 5
    assert "matchingRuns" in api
    assert "briefs" in api
    assert "guaranteed investment" not in script.lower()
    assert "recommended investment" not in script.lower()


def test_investor_thesis_is_versioned_and_unknown_criteria_are_preserved() -> None:
    script = (INVESTOR / "app.js").read_text(encoding="utf-8")
    assert "expected_version_id" in script
    assert "profileVersions" in script
    assert "Enregistrer une nouvelle version" in script
    assert "UNKNOWN" in script
    assert "state.profile.current_version_id" in script
