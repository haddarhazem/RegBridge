"""Shared fixtures for real-browser RegBridge acceptance journeys.

These fixtures intentionally do not create tokens or bypass the OIDC redirect.
They require an explicitly configured local/test application stack and use only
synthetic accounts and data.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import pytest

pytest.importorskip("playwright", reason="install the browser optional dependency to run browser_e2e")

import pytest_asyncio
from playwright.async_api import Browser, Page, async_playwright, expect
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.compliance.models import (
    ComplianceControlDefinition,
    ComplianceFramework,
    ComplianceFrameworkVersion,
    ControlEvidenceLink,
    ProjectComplianceControl,
    ProjectFrameworkAdoption,
)
from app.modules.investment.brief_models import InvestorOpportunityBriefRun
from app.modules.investment.matching_models import MatchingRun
from app.modules.projects.models import Project, ProjectMember
from app.modules.projects.profile_models import StartupProfile, StartupProfileRevision


pytestmark = pytest.mark.browser_e2e


def _base_url() -> str:
    value = os.getenv("BROWSER_E2E_BASE_URL", "").strip()
    if not value:
        pytest.skip("BROWSER_E2E_BASE_URL is required for browser_e2e")
    return value.rstrip("/")


def _password() -> str:
    value = os.getenv("BROWSER_E2E_PASSWORD", "")
    if not value:
        pytest.skip("BROWSER_E2E_PASSWORD is required and must be synthetic")
    return value


def _artifact_path(node_name: str, suffix: str) -> Path:
    root = Path(os.getenv("BROWSER_E2E_ARTIFACT_DIR", "artifacts/browser-e2e"))
    root.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", node_name)
    return root / f"{safe_name}{suffix}"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    setattr(item, f"rep_{call.when}", outcome.get_result())


@pytest_asyncio.fixture
async def chromium() -> Browser:
    _base_url()
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=os.getenv("BROWSER_E2E_HEADLESS", "1") != "0")
        except Exception as exc:
            pytest.fail(f"Chromium could not launch; run `python -m playwright install chromium`: {type(exc).__name__}")
        yield browser
        await browser.close()


@pytest_asyncio.fixture
async def browser_page(request, chromium: Browser) -> Page:
    context = await chromium.new_context(base_url=_base_url(), viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    try:
        yield page
    finally:
        failed = getattr(request.node, "rep_call", None)
        if failed is not None and failed.failed:
            await page.screenshot(path=str(_artifact_path(request.node.name, ".png")), full_page=True)
        await context.close()


@pytest_asyncio.fixture
async def traced_harness_page(request, chromium: Browser) -> Page:
    """Unauthenticated harness page with a safe trace for bootstrap failures."""

    context = await chromium.new_context(base_url=_base_url())
    await context.tracing.start(screenshots=True, snapshots=True, sources=False)
    page = await context.new_page()
    try:
        yield page
    finally:
        failed = getattr(request.node, "rep_call", None)
        if failed is not None and failed.failed:
            await page.screenshot(path=str(_artifact_path(request.node.name, ".png")), full_page=True)
            await context.tracing.stop(path=str(_artifact_path(request.node.name, ".zip")))
        else:
            await context.tracing.stop()
        await context.close()


@pytest.fixture
def synthetic_user() -> dict[str, str]:
    identity = uuid.uuid4().hex[:12]
    return {
        "email": f"regbridge-e2e-{identity}@example.test",
        "password": _password(),
    }


@pytest_asyncio.fixture
async def e2e_compliance_framework() -> str:
    """Provide one disposable framework version with a materialized control."""

    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    framework_id = version_id = None
    try:
        async with factory() as session:
            framework = ComplianceFramework(stable_key=f"E2E-{uuid.uuid4().hex}", name="E2E Compliance Framework")
            session.add(framework)
            await session.flush()
            version = ComplianceFrameworkVersion(framework_id=framework.id, version_identifier="V1", status="active")
            session.add(version)
            await session.flush()
            session.add(ComplianceControlDefinition(
                framework_version_id=version.id,
                stable_key="E2E-001",
                title="E2E synthetic compliance control",
                description="Synthetic control used only by the disposable browser journey.",
                source_references=[{"source_id": "e2e-synthetic-source"}],
            ))
            await session.commit()
            framework_id, version_id = framework.id, version.id
        yield str(version_id)
    finally:
        if version_id is not None:
            async with factory() as session:
                control_ids = select(ProjectComplianceControl.id).where(ProjectComplianceControl.framework_version_id == version_id)
                await session.execute(delete(ControlEvidenceLink).where(ControlEvidenceLink.project_control_id.in_(control_ids)))
                await session.execute(delete(ProjectComplianceControl).where(ProjectComplianceControl.framework_version_id == version_id))
                await session.execute(delete(ProjectFrameworkAdoption).where(ProjectFrameworkAdoption.framework_version_id == version_id))
                await session.execute(delete(ComplianceControlDefinition).where(ComplianceControlDefinition.framework_version_id == version_id))
                await session.execute(delete(ComplianceFrameworkVersion).where(ComplianceFrameworkVersion.id == version_id))
                await session.execute(delete(ComplianceFramework).where(ComplianceFramework.id == framework_id))
                await session.commit()
        await engine.dispose()


@pytest_asyncio.fixture
async def e2e_investor_startups() -> dict[str, str]:
    """Create disposable public and private startup controls for investor E2E.

    The public startup is the only startup the browser should discover.  The
    private control carries a sentinel that must never reach the investor
    projection.  Both records are synthetic and are removed in dependency
    order after the test.
    """

    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owner_id = public_id = private_id = None
    marker = uuid.uuid4().hex[:10]
    public_name = f"E2E Startup Alpha {marker}"
    private_name = f"E2E Private Control {marker}"
    try:
        async with factory() as session:
            owner = User(email=f"regbridge-e2e-startup-owner-{marker}@example.test")
            session.add(owner)
            await session.flush()

            public_project = Project(
                owner_user_id=owner.id,
                project_type="existing_startup",
                display_name=public_name,
                raw_description="Synthetic public startup for investor browser acceptance.",
                sector="SaaS",
                technology="Cloud",
                location="France",
                current_progress="Seed",
                visibility="public",
                onboarding_status="complete",
                confirmed_fields={},
            )
            private_project = Project(
                owner_user_id=owner.id,
                project_type="existing_startup",
                display_name=private_name,
                raw_description="Synthetic private control; it must never be discoverable.",
                sector="SaaS",
                technology="Cloud",
                location="France",
                current_progress="Seed",
                visibility="private",
                onboarding_status="complete",
                confirmed_fields={},
            )
            session.add_all([public_project, private_project])
            await session.flush()
            owner_id, public_id, private_id = owner.id, public_project.id, private_project.id
            session.add_all([
                ProjectMember(project_id=public_project.id, user_id=owner.id, member_role="owner", status="active"),
                ProjectMember(project_id=private_project.id, user_id=owner.id, member_role="owner", status="active"),
            ])
            for project in (public_project, private_project):
                profile = StartupProfile(project_id=project.id, current_revision=1)
                session.add(profile)
                await session.flush()
                snapshot = [
                    {"field_name": "description", "section": "public", "value": "Cloud compliance operations for French SMEs.", "visibility": "PUBLIC"},
                    {"field_name": "investor_summary", "section": "public", "value": "Synthetic startup with authorized public information.", "visibility": "PUBLIC"},
                    {"field_name": "internal_notes", "section": "private", "value": f"PRIVATE_E2E_SENTINEL_{marker}", "visibility": "PRIVATE"},
                ]
                if project.id == private_project.id:
                    snapshot = [
                        {"field_name": "description", "section": "private", "value": "PRIVATE_E2E_SENTINEL_DESCRIPTION", "visibility": "PRIVATE"},
                        {"field_name": "internal_notes", "section": "private", "value": f"PRIVATE_E2E_SENTINEL_{marker}", "visibility": "PRIVATE"},
                    ]
                session.add(StartupProfileRevision(profile_id=profile.id, revision_number=1, snapshot=snapshot, changed_by_user_id=owner.id))
            await session.commit()
        yield {"public_id": str(public_id), "public_name": public_name, "private_id": str(private_id), "private_name": private_name}
    finally:
        if owner_id is not None:
            async with factory() as session:
                project_ids = [item for item in (public_id, private_id) if item is not None]
                if project_ids:
                    await session.execute(delete(AuditLog).where(AuditLog.project_id.in_(project_ids)))
                    await session.execute(delete(InvestorOpportunityBriefRun).where(InvestorOpportunityBriefRun.startup_project_id.in_(project_ids)))
                    await session.execute(delete(MatchingRun).where(MatchingRun.startup_project_id.in_(project_ids)))
                    profile_ids = select(StartupProfile.id).where(StartupProfile.project_id.in_(project_ids))
                    await session.execute(delete(StartupProfileRevision).where(StartupProfileRevision.profile_id.in_(profile_ids)))
                    await session.execute(delete(StartupProfile).where(StartupProfile.project_id.in_(project_ids)))
                    await session.execute(delete(ProjectMember).where(ProjectMember.project_id.in_(project_ids)))
                    await session.execute(delete(Project).where(Project.id.in_(project_ids)))
                await session.execute(delete(User).where(User.id == owner_id))
                await session.commit()
        await engine.dispose()


async def authenticate(page: Page, user: dict[str, str], *, register: bool = True) -> None:
    route = "/auth/register/" if register else "/auth/login/"
    await page.goto(route)
    await page.get_by_role("button", name=re.compile("organisation", re.IGNORECASE)).click()
    await page.wait_for_url(re.compile(r"/realms/regbridge/|/protocol/openid-connect/"), timeout=30_000)

    if register:
        register_link = page.get_by_role("link", name=re.compile("^Register$", re.IGNORECASE))
        if await register_link.count():
            await register_link.click()
        await page.locator("input[name='username']").fill(user["email"])
        if await page.locator("input[name='email']").count():
            await page.locator("input[name='email']").fill(user["email"])
        if await page.locator("input[name='firstName']").count():
            await page.locator("input[name='firstName']").fill("RegBridge")
        if await page.locator("input[name='lastName']").count():
            await page.locator("input[name='lastName']").fill("E2E")
        await page.locator("input[name='password']").fill(user["password"])
        await page.locator("input[name='password-confirm']").fill(user["password"])
        register_submit = page.get_by_role("button", name=re.compile("Register", re.IGNORECASE))
        if await register_submit.count():
            await register_submit.click()
        else:
            await page.locator("input[type='submit']").click()
    else:
        await page.locator("input[name='username']").fill(user["email"])
        await page.locator("input[name='password']").fill(user["password"])
        login_submit = page.get_by_role("button", name=re.compile("^Sign In$", re.IGNORECASE))
        if await login_submit.count():
            await login_submit.click()
        else:
            await page.locator("input[type='submit']").click()

    await page.wait_for_url(re.compile(r"127\.0\.0\.1:8000/(onboarding/roles|entrepreneur/)"), timeout=30_000)
    await page.wait_for_load_state("domcontentloaded")
    if "/onboarding/roles/" in page.url:
        entrepreneur_role = page.locator("input[type='checkbox'][value='entrepreneur']")
        await expect(entrepreneur_role).to_have_count(1, timeout=30_000)
        await entrepreneur_role.check()
        await page.get_by_role("button", name=re.compile("Continuer", re.IGNORECASE)).click()
    await page.wait_for_url(re.compile(r"127\.0\.0\.1:8000/entrepreneur/"), timeout=30_000)
    await expect(page.locator("[data-sidebar-nav]")).to_contain_text("Tableau")


async def authenticate_investor(page: Page, user: dict[str, str], *, register: bool = True) -> None:
    """Authenticate one synthetic account and select the actual investor role."""

    route = "/auth/register/" if register else "/auth/login/"
    await page.goto(route)
    await page.get_by_role("button", name=re.compile("organisation", re.IGNORECASE)).click()
    await page.wait_for_url(re.compile(r"/realms/regbridge/|/protocol/openid-connect/"), timeout=30_000)

    if register:
        register_link = page.get_by_role("link", name=re.compile("^Register$", re.IGNORECASE))
        if await register_link.count():
            await register_link.click()
        await page.locator("input[name='username']").fill(user["email"])
        if await page.locator("input[name='email']").count():
            await page.locator("input[name='email']").fill(user["email"])
        if await page.locator("input[name='firstName']").count():
            await page.locator("input[name='firstName']").fill("RegBridge")
        if await page.locator("input[name='lastName']").count():
            await page.locator("input[name='lastName']").fill("Investor E2E")
        await page.locator("input[name='password']").fill(user["password"])
        await page.locator("input[name='password-confirm']").fill(user["password"])
        submit = page.get_by_role("button", name=re.compile("Register", re.IGNORECASE))
        await (submit if await submit.count() else page.locator("input[type='submit']")).click()
    else:
        await page.locator("input[name='username']").fill(user["email"])
        await page.locator("input[name='password']").fill(user["password"])
        submit = page.get_by_role("button", name=re.compile("^Sign In$", re.IGNORECASE))
        await (submit if await submit.count() else page.locator("input[type='submit']")).click()

    await page.wait_for_url(re.compile(r"127\.0\.0\.1:8000/(onboarding/roles|investor/)"), timeout=30_000)
    await page.wait_for_load_state("domcontentloaded")
    if "/onboarding/roles/" in page.url:
        investor_role = page.locator("input[type='checkbox'][value='investor']")
        await expect(investor_role).to_have_count(1, timeout=30_000)
        await investor_role.check()
        await page.get_by_role("button", name=re.compile("Continuer", re.IGNORECASE)).click()
    await page.wait_for_url(re.compile(r"127\.0\.0\.1:8000/investor/"), timeout=30_000)
    await expect(page.locator("[data-investor-workspace]")).to_be_visible(timeout=30_000)
    await expect(page.locator("[data-investor-loading]")).to_be_hidden(timeout=30_000)


async def create_project(page: Page, description: str = "RegBridge synthetic service for French businesses.") -> str:
    project_name = f"E2E Projet {uuid.uuid4().hex[:8]}"
    await page.get_by_role("button", name=re.compile("premier projet", re.IGNORECASE)).click()
    await page.get_by_label("Nom du projet").fill(project_name)
    await page.locator("textarea[name='raw_description']").fill(description)
    await page.locator("button[data-action='submit-create']").click()
    await expect(page.locator("[data-project-switcher]")).to_contain_text(project_name)
    return project_name


async def complete_onboarding(page: Page, values: dict[str, str] | None = None) -> None:
    for _ in range(8):
        await expect(page.locator('[data-workspace]')).to_have_attribute('aria-busy', 'false')
        form = page.locator("form[data-form='onboarding']")
        if not await form.count():
            return
        current_field = await form.get_attribute("data-field")
        await form.locator("textarea[name='value']").fill((values or {}).get(current_field, "Synthetic RegBridge test information."))
        await form.locator("input[name='confirm']").check()
        await form.get_by_role("button", name=re.compile("Enregistrer et continuer", re.IGNORECASE)).click()
        await page.wait_for_function(
            """previousField => {
                if (document.querySelector('[data-workspace]').getAttribute('aria-busy') === 'true') return false;
                const nextForm = document.querySelector("form[data-form='onboarding']");
                return !nextForm || nextForm.dataset.field !== previousField;
            }""",
            arg=current_field,
            timeout=30_000,
        )
    pytest.fail("Onboarding did not reach a bounded terminal state")
