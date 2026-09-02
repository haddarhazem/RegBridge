from __future__ import annotations

import re

import pytest
from playwright.async_api import expect

from .conftest import authenticate_investor


pytestmark = pytest.mark.browser_e2e


@pytest.mark.e2e
async def test_landing_role_navigation_selects_informational_pathways(browser_page) -> None:
    await browser_page.goto("/")

    for role, index in (("startup", 0), ("investor", 1), ("researcher", 2)):
        await browser_page.locator(f"header [data-pathway-role='{role}']").click()
        await expect(browser_page).to_have_url(re.compile(r"/#pathways$"))
        await expect(browser_page.locator(f"[data-role-tab='{index}']")).to_have_class(re.compile(r"\bis-active\b"))
        assert "/entrepreneur/" not in browser_page.url
        assert "/investor/" not in browser_page.url
        assert "/workspace/" not in browser_page.url


@pytest.mark.e2e
async def test_active_session_does_not_redirect_landing_auth_links(browser_page, synthetic_user) -> None:
    await authenticate_investor(browser_page, synthetic_user)
    await browser_page.goto("/")

    await browser_page.locator("header .login-link").click()
    await expect(browser_page).to_have_url(re.compile(r"/auth/login/$"))
    await expect(browser_page.locator("#login-title")).to_be_visible()
    await expect(browser_page.locator("[data-auth-continue]")).to_be_visible(timeout=30_000)
    assert "/investor/" not in browser_page.url

    await browser_page.goto("/")
    await browser_page.locator("header a[href='/auth/register/']").click()
    await expect(browser_page).to_have_url(re.compile(r"/auth/register/$"))
    await expect(browser_page.locator("[data-auth-continue]")).to_be_visible(timeout=30_000)
    assert "/investor/" not in browser_page.url


@pytest.mark.e2e
async def test_active_auth_page_requires_explicit_workspace_continuation(browser_page, synthetic_user) -> None:
    await authenticate_investor(browser_page, synthetic_user)
    await browser_page.goto("/auth/login/")
    await expect(browser_page.locator("[data-auth-continue]")).to_be_visible(timeout=30_000)
    assert "/investor/" not in browser_page.url

    await browser_page.locator("[data-auth-continue]").click()
    await expect(browser_page).to_have_url(re.compile(r"/investor/$"), timeout=30_000)
