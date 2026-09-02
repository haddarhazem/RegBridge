from __future__ import annotations

import re

import pytest
from playwright.async_api import expect

from .conftest import authenticate_investor


pytestmark = pytest.mark.browser_e2e


async def _wait_for_investor(page) -> None:
    await expect(page.locator("[data-investor-loading]")).to_be_hidden(timeout=30_000)
    await expect(page.locator("[data-investor-workspace]")).to_be_visible(timeout=30_000)


@pytest.mark.e2e
async def test_investor_startup_matching_brief_persistence_and_authorization(
    browser_page,
    chromium,
    synthetic_user,
    e2e_investor_startups,
):
    """Exercise the investor journey against real OIDC, API, PostgreSQL and UI state."""

    startup = e2e_investor_startups
    await authenticate_investor(browser_page, synthetic_user)

    # A thesis is required before the matching endpoint can be used.
    await browser_page.goto("/investor/?view=thesis")
    await _wait_for_investor(browser_page)
    thesis_form = browser_page.locator("[data-thesis-form]")
    await thesis_form.locator("input[name='sectors']").fill("SaaS")
    await thesis_form.locator("input[name='stages']").fill("Seed")
    await thesis_form.locator("input[name='geographies']").fill("France")
    await thesis_form.locator("input[name='technologies']").fill("Cloud")
    await thesis_form.get_by_role("button", name=re.compile("créer ma thèse", re.IGNORECASE)).click()
    await expect(browser_page.locator("[data-thesis-form]")).to_contain_text("Modifier la version", timeout=30_000)

    # Discovery is query-time authorized. The private control and its sentinel
    # must not be present in either the filtered result or the page body.
    await browser_page.goto("/investor/?view=discovery")
    await _wait_for_investor(browser_page)
    discovery_form = browser_page.locator("[data-discovery-form]")
    await discovery_form.locator("input[name='sector']").fill("SaaS")
    await discovery_form.get_by_role("button", name=re.compile("rechercher", re.IGNORECASE)).click()
    await _wait_for_investor(browser_page)
    await expect(browser_page.locator(".investor-startup-card").filter(has_text=startup["public_name"])).to_have_count(1)
    body = await browser_page.locator("body").inner_text()
    assert startup["private_name"] not in body
    assert "PRIVATE_E2E_SENTINEL" not in body

    # Discovery -> startup detail.
    public_card = browser_page.locator(".investor-startup-card").filter(has_text=startup["public_name"])
    await public_card.locator("[data-open-startup]").click()
    await _wait_for_investor(browser_page)
    await expect(browser_page).to_have_url(re.compile(r"view=detail"))
    await expect(browser_page.get_by_role("heading", name=startup["public_name"])).to_be_visible()
    await expect(browser_page.locator(".investor-detail-main")).to_contain_text("Cloud compliance operations")
    detail_body = await browser_page.locator("body").inner_text()
    assert startup["private_name"] not in detail_body
    assert "PRIVATE_E2E_SENTINEL" not in detail_body

    # Detail -> deterministic structured matching. Four dimensions match and
    # the missing ticket remains UNKNOWN rather than becoming a mismatch.
    await browser_page.locator("[data-analyze-startup]").click()
    await _wait_for_investor(browser_page)
    await expect(browser_page).to_have_url(re.compile(r"view=match&match="))
    await expect(browser_page.locator(".investor-match-dimension")).to_have_count(5)
    await expect(browser_page.locator(".investor-match-match")).to_have_count(4)
    await expect(browser_page.locator(".investor-match-unknown")).to_have_count(1)
    match_body = await browser_page.locator("body").inner_text()
    assert "Information insuffisante" in match_body
    assert "MISMATCH" not in match_body
    assert "UNKNOWN" not in match_body
    assert not re.search(r"\b(ROI|valorisation|rendement|rentabilit[eé]|probabilit[eé] de succ[eè]s)\b", match_body, re.IGNORECASE)
    match_id = re.search(r"[?&]match=([^&]+)", browser_page.url).group(1)

    # Matching -> persisted brief, then reload and owner lists.
    await browser_page.locator("[data-create-brief]").click()
    await _wait_for_investor(browser_page)
    await expect(browser_page).to_have_url(re.compile(r"view=brief&brief="))
    brief_id = re.search(r"[?&]brief=([^&]+)", browser_page.url).group(1)
    await expect(browser_page.locator(".investor-brief-content section")).to_have_count(5)
    await expect(browser_page.locator(".investor-brief-content")).to_contain_text("Executive summary")
    brief_body = await browser_page.locator("body").inner_text()
    assert startup["public_name"] in brief_body
    assert not re.search(r"\b(ROI|valorisation|rendement|rentabilit[eé]|probabilit[eé] de succ[eè]s)\b", brief_body, re.IGNORECASE)
    await browser_page.reload()
    await _wait_for_investor(browser_page)
    await expect(browser_page.locator(".investor-brief-content section")).to_have_count(5)

    await browser_page.locator("[data-nav-view='matches']").click()
    await _wait_for_investor(browser_page)
    match_card = browser_page.locator(".investor-list-card").filter(has_text=startup["public_name"])
    await expect(match_card).to_have_count(1)
    await match_card.locator("a[href*='view=match']").click()
    await _wait_for_investor(browser_page)
    await expect(browser_page).to_have_url(re.compile(rf"match={re.escape(match_id)}"))
    await browser_page.locator("[data-nav-view='briefs']").click()
    await _wait_for_investor(browser_page)
    brief_card = browser_page.locator(".investor-list-card").filter(has_text=startup["public_name"])
    await expect(brief_card).to_have_count(1)
    await brief_card.locator("a[href*='view=brief']").filter(has_text="Ouvrir").click()
    await _wait_for_investor(browser_page)
    await expect(browser_page).to_have_url(re.compile(rf"brief={re.escape(brief_id)}"))

    # Logout/relogin proves the match and brief are backed by the real store.
    await browser_page.locator("[data-logout]").click()
    await browser_page.wait_for_url(re.compile(r"/auth/login/"), timeout=30_000)
    await authenticate_investor(browser_page, synthetic_user, register=False)
    await browser_page.goto("/investor/?view=matches")
    await _wait_for_investor(browser_page)
    await expect(browser_page.locator(".investor-list-card").filter(has_text=startup["public_name"])).to_have_count(1)
    await browser_page.goto("/investor/?view=briefs")
    await _wait_for_investor(browser_page)
    await expect(browser_page.locator(".investor-list-card").filter(has_text=startup["public_name"])).to_have_count(1)

    # A second investor can authenticate, but cannot read the first investor's
    # private matching or brief resources.
    other_user = {"email": f"regbridge-e2e-other-{match_id[:12]}@example.test", "password": synthetic_user["password"]}
    second_context = await chromium.new_context(base_url=browser_page.url.split("/investor/")[0], viewport={"width": 1440, "height": 900})
    second_page = await second_context.new_page()
    try:
        await authenticate_investor(second_page, other_user)
        await second_page.goto(f"/investor/?view=match&match={match_id}")
        await _wait_for_investor(second_page)
        await expect(second_page.locator(".investor-inline-error")).to_contain_text("accès", timeout=30_000)
        await second_page.goto(f"/investor/?view=brief&brief={brief_id}")
        await _wait_for_investor(second_page)
        await expect(second_page.locator(".investor-inline-error")).to_contain_text("accès", timeout=30_000)
        second_body = await second_page.locator("body").inner_text()
        assert startup["public_name"] not in second_body
        assert "PRIVATE_E2E_SENTINEL" not in second_body
    finally:
        await second_context.close()
