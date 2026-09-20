"""Optional real-browser acceptance for the derived project graph."""

import re

import pytest
from playwright.async_api import expect

from .conftest import authenticate, complete_onboarding, create_project


pytestmark = pytest.mark.browser_e2e


async def test_project_graph_is_readable_interactive_and_uses_confirmed_data(browser_page, synthetic_user):
    page = browser_page
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    await authenticate(page, synthetic_user)
    description = "Service numérique de téléconsultation pour des cabinets professionnels."
    await create_project(page, description)
    await page.wait_for_url(re.compile(r"view=onboarding"), timeout=10_000)
    await complete_onboarding(page, {
        "activity": "Service de téléconsultation",
        "sector": "Santé numérique",
        "technology": "Application web sécurisée",
        "data": "Données de contact des utilisateurs",
        "market": "Cabinets professionnels",
        "location": "Belgique",
    })
    await expect(page.locator('[data-workspace]')).not_to_contain_text(description)
    await page.locator('[data-nav-view="project"]').click()
    await page.locator('[data-action="project-tab"][data-tab="graph"]').click()
    canvas = page.locator('.project-graph-canvas')
    await expect(canvas).to_be_visible()
    await expect(page.locator('[data-graph-filter]')).to_have_count(7)
    await page.mouse.move(500, 400)
    await page.mouse.down()
    await page.mouse.move(590, 450)
    await page.mouse.up()
    await page.mouse.wheel(0, -200)
    await page.locator('[data-graph-filter="DATA_CATEGORY"]').click()
    await expect(page.locator('[data-graph-filter="DATA_CATEGORY"]')).to_have_attribute("aria-pressed", "false")
    await page.locator('[data-graph-reset]').click()
    await expect(page.locator('[data-graph-details]')).to_contain_text("Sélectionnez un nœud")
    assert not errors


async def test_project_graph_preserves_sector_and_geography_modality_in_the_rendered_ui(browser_page, synthetic_user):
    """Exercise the V1.2.2 semantic boundary through the user-facing workspace."""

    page = browser_page
    await authenticate(page, synthetic_user)
    await create_project(
        page,
        "Un logiciel B2B pour les entreprises clientes, lancé en France avant une possible expansion dans l’Union européenne.",
    )
    await complete_onboarding(page, {
        "activity": "Plateforme de gestion énergétique",
        "sector": "EnergyTech / SaaS B2B",
        "technology": "intelligence artificielle",
        "data": "données personnelles des clients",
        "market": "France",
        "location": "Île-de-France, France",
    })
    await page.get_by_role("link", name=re.compile("Mon projet", re.IGNORECASE)).click()
    await page.locator('[data-action="project-tab"][data-tab="graph"]').click()
    relations = page.locator('[data-graph-relations]')
    await expect(relations).to_contain_text("EnergyTech / SaaS B2B")
    await expect(relations).to_contain_text("Île-de-France, France")
    await expect(relations).to_contain_text("France")
    rendered = await page.locator('[data-project-graph]').inner_text()
    assert "logiciel B2B" not in rendered
    assert "Union européenne" not in rendered
    assert "HAS_SECTOR" not in rendered
    assert "OPERATES_IN" not in rendered
    assert "PROJECT_GRAPH" not in rendered
    assert "Modèle économique" not in rendered
    assert "Secteur" in rendered
    assert "Marché cible" in rendered
    assert "Localisation / opère dans" in rendered

    await page.locator('[data-open-copilot]').click()
    for question, expected in (
        ("Quel est le secteur de ce projet ?", "EnergyTech / SaaS B2B"),
        ("Où ce projet opère-t-il actuellement ?", "Île-de-France, France"),
        ("Quel est le marché cible ?", "France"),
        ("Est-ce que ce projet opère actuellement dans toute l'Union européenne ?", "Île-de-France, France"),
    ):
        await page.locator('#copilot-question').fill(question)
        async with page.expect_response(
            lambda response: response.request.method == "POST" and response.url.endswith("/responses"),
            timeout=30_000,
        ) as response_info:
            await page.locator('[data-copilot-form]').get_by_role("button", name="Envoyer").click()
        assert (await response_info.value).status == 201
        await expect(page.locator('.copilot-message-assistant').last).to_contain_text(expected, timeout=30_000)
