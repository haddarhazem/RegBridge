from __future__ import annotations

import re
import uuid

import pytest
from playwright.async_api import expect

from .conftest import authenticate, complete_onboarding, create_project


pytestmark = pytest.mark.browser_e2e


async def test_browser_harness_launches_chromium_reads_dom_and_has_safe_trace(traced_harness_page):
    await traced_harness_page.goto("/auth/login/")
    await expect(traced_harness_page).to_have_title(re.compile("Connexion", re.IGNORECASE))
    await expect(traced_harness_page.get_by_role("heading", name=re.compile("Retrouvez", re.IGNORECASE))).to_be_visible()


@pytest.mark.e2e
async def test_entrepreneur_critical_journey_logout_relogin_and_persistence(browser_page, synthetic_user):
    await authenticate(browser_page, synthetic_user)
    project_name = await create_project(browser_page)
    await complete_onboarding(browser_page)

    await browser_page.reload()
    await expect(browser_page.locator("[data-project-switcher]")).to_contain_text(project_name)
    await browser_page.get_by_role("link", name=re.compile("Mon projet", re.IGNORECASE)).click()
    await expect(browser_page.get_by_role("heading", name=re.compile(project_name))).to_be_visible()
    await browser_page.get_by_role("link", name=re.compile("Profil", re.IGNORECASE)).click()
    await browser_page.locator("[data-logout]").click()
    await browser_page.wait_for_url(re.compile(r"/auth/login/"), timeout=30_000)

    await authenticate(browser_page, synthetic_user, register=False)
    await expect(browser_page.locator("[data-project-switcher]")).to_contain_text(project_name)


@pytest.mark.e2e
async def test_second_user_cannot_open_first_users_project(browser_page, synthetic_user):
    await authenticate(browser_page, synthetic_user)
    project_name = await create_project(browser_page)
    project_id = await browser_page.evaluate(
        """() => Object.keys(localStorage)
            .filter((key) => key.endsWith('.active-project'))
            .map((key) => localStorage.getItem(key))
            .find(Boolean)"""
    )
    assert project_id
    second_user = {
        "email": f"regbridge-e2e-{uuid.uuid4().hex[:12]}@example.test",
        "password": synthetic_user["password"],
    }
    await browser_page.locator("[data-logout]").click()
    await browser_page.wait_for_url(re.compile(r"/auth/login/"), timeout=30_000)
    await authenticate(browser_page, second_user)
    await browser_page.goto(f"/entrepreneur/?view=project&project={project_id}")
    await expect(browser_page.locator(".inline-error")).to_contain_text("projet", timeout=30_000)
    await expect(browser_page.locator("[data-workspace]")).not_to_contain_text(project_name)


@pytest.mark.e2e
async def test_document_native_extraction_journey(browser_page, synthetic_user):
    await authenticate(browser_page, synthetic_user)
    await create_project(browser_page)
    await browser_page.get_by_role("link", name=re.compile("Documents", re.IGNORECASE)).click()
    await browser_page.get_by_role("button", name=re.compile("Importer un document", re.IGNORECASE)).click()
    await browser_page.locator("form[data-form='upload-document'] input[type='file']").set_input_files({
        "name": "e2e-native.txt",
        "mimeType": "text/plain",
        "buffer": b"RegBridge synthetic native extraction content for browser E2E validation.",
    })
    await browser_page.locator("form[data-form='upload-document'] input[name='title']").fill("E2E Native Extraction")
    await browser_page.locator("button[data-action='submit-upload']").click()
    await expect(browser_page.locator(".document-list")).to_contain_text("e2e-native.txt", timeout=30_000)
    document_row = browser_page.locator(".document-list .document-row").filter(has_text="e2e-native.txt")
    await expect(document_row.locator(".status-badge").last).to_be_visible(timeout=30_000)
    await browser_page.reload()
    document_row = browser_page.locator(".document-list .document-row").filter(has_text="e2e-native.txt")
    await expect(document_row.locator(".status-badge").last).to_be_visible(timeout=30_000)


@pytest.mark.e2e
async def test_compliance_journey_uses_real_framework_and_control_state(browser_page, synthetic_user, e2e_compliance_framework):
    await authenticate(browser_page, synthetic_user)
    await create_project(browser_page)
    await complete_onboarding(browser_page)
    await browser_page.get_by_role("link", name=re.compile("Mon projet", re.IGNORECASE)).click()
    transition = browser_page.get_by_role("button", name=re.compile("Passer en startup", re.IGNORECASE))
    await expect(transition).to_be_visible(timeout=30_000)
    await transition.click()
    await browser_page.goto("/entrepreneur/?view=compliance")
    await expect(browser_page.get_by_role("heading", name=re.compile(r"^Contr.*et preuves$", re.IGNORECASE))).to_be_visible()
    framework = browser_page.locator("[data-compliance-framework]")
    if await framework.count() == 0:
        pytest.skip("No active compliance framework is available in this environment")
    await framework.select_option(value=e2e_compliance_framework)
    adopt = browser_page.get_by_role("button", name=re.compile("Activer ce r", re.IGNORECASE))
    await expect(adopt).to_be_visible(timeout=30_000)
    await adopt.click()
    await expect(browser_page.locator(".control-list")).to_be_visible(timeout=30_000)
