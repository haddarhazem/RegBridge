from pathlib import Path

import httpx
import pytest

from app.main import app


ROOT = Path(__file__).parents[1] / "frontend"
AUTH = ROOT / "auth"


@pytest.mark.asyncio
async def test_authentication_routes_and_canonical_onboarding_are_served() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        responses = {
            path: await client.get(path)
            for path in (
                "/auth/login/",
                "/auth/register/",
                "/auth/callback/",
                "/onboarding/roles/",
                "/workspace/",
                "/auth/roles/",
            )
        }

    assert all(response.status_code == 200 for response in responses.values())
    assert 'data-auth-page="login"' in responses["/auth/login/"].text
    assert 'data-auth-page="register"' in responses["/auth/register/"].text
    assert 'data-auth-page="callback"' in responses["/auth/callback/"].text
    assert 'data-auth-page="onboarding"' in responses["/onboarding/roles/"].text
    assert 'data-auth-page="workspace"' in responses["/workspace/"].text
    assert 'url=/onboarding/roles/' in responses["/auth/roles/"].text


def test_browser_auth_uses_oidc_code_pkce_library_and_centralized_bearer_client() -> None:
    runtime = (AUTH / "auth-runtime.js").read_text(encoding="utf-8")
    ui = (AUTH / "auth.js").read_text(encoding="utf-8")
    login = (AUTH / "login" / "index.html").read_text(encoding="utf-8")
    license_text = (ROOT / "vendor" / "oidc-client-ts" / "LICENSE").read_text(encoding="utf-8")

    assert "oidc-client-ts.min.js" in login
    assert "new window.oidc.UserManager" in runtime
    assert "response_type: 'code'" in runtime
    assert "WebStorageStateStore({ store: window.sessionStorage })" in runtime
    assert "signinRedirect(" in runtime
    assert "signinRedirectCallback()" in runtime
    assert "signoutRedirect()" in runtime
    assert "Authorization', `Bearer ${user.access_token}`" in runtime
    assert "apiRequest('/me')" in runtime
    assert "apiRequest('/me/roles/options')" in runtime
    assert "method: 'PUT'" in runtime
    assert "Authorization" not in ui
    assert "access_token" not in ui
    assert "setAccessToken" not in runtime + ui
    assert "localStorage" not in runtime + ui
    assert "client_secret" not in runtime + ui
    assert "Apache License" in license_text


def test_auth_pages_preserve_design_accessibility_and_real_role_semantics() -> None:
    pages = [
        (AUTH / "login" / "index.html").read_text(encoding="utf-8"),
        (AUTH / "register" / "index.html").read_text(encoding="utf-8"),
        (ROOT / "onboarding" / "roles" / "index.html").read_text(encoding="utf-8"),
        (ROOT / "workspace" / "index.html").read_text(encoding="utf-8"),
    ]
    onboarding = pages[2]
    script = (AUTH / "auth.js").read_text(encoding="utf-8")
    css = (AUTH / "auth.css").read_text(encoding="utf-8")

    for page in pages:
        assert page.count("<h1") == 1
        assert 'class="auth-visual' in page
        assert 'class="auth-panel"' in page
        assert 'data-auth-state' in page
        assert 'oidc-client-ts.min.js' in page
    assert '<fieldset class="role-fieldset">' in onboarding
    assert '<legend>Rôles disponibles</legend>' in onboarding
    assert "input.type = 'checkbox'" in script
    assert "dataRoleCheckbox" not in script
    assert "data-role-checkbox" in script
    assert "runtime.roleOptions()" in script
    assert "runtime.replaceRoles(selectedRoles())" in script
    assert "admin" not in script
    assert "research_center" not in script
    assert "startup:" not in script
    assert "prefers-reduced-motion: reduce" in css
    assert ".role-option:has(input:focus-visible)" in css


def test_auth_has_safe_redirects_no_branded_provider_and_no_fake_password_routes() -> None:
    runtime = (AUTH / "auth-runtime.js").read_text(encoding="utf-8")
    pages = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.rglob("index.html"))

    assert "target.origin !== window.location.origin" in runtime
    assert "target.pathname.startsWith('/auth/callback')" in runtime
    assert "Google" not in pages
    assert "Apple" not in pages
    assert "LinkedIn" not in pages
    assert "/auth/reset-password" not in pages
    assert "console.log" not in runtime
