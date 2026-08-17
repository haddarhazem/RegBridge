import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.main import app
from app.modules.projects.authorization import ProjectAuthorizationPolicy
from app.modules.projects.router import project_response


def member(role: str, status: str = "active") -> SimpleNamespace:
    return SimpleNamespace(member_role=role, status=status)


def project(visibility: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        project_type="idea",
        display_name="Example",
        visibility=visibility,
        raw_description="private details",
        user_goal=None,
        current_progress=None,
        country_code="FR",
        target_market="France",
        language="fr",
        owner_user_id=uuid.uuid4(),
    )


def test_policy_is_fail_closed_for_inactive_memberships() -> None:
    policy = ProjectAuthorizationPolicy()
    private_project = project("private")

    assert policy.can_view(private_project, None) is False
    assert policy.can_view(private_project, member("member", "invited")) is False
    assert policy.can_view(private_project, member("member", "revoked")) is False
    assert policy.can_edit(member("viewer")) is False
    assert policy.can_manage_members(member("member")) is False


def test_visibility_allows_only_safe_non_member_summary() -> None:
    response = project_response(project("public"), None)

    assert response.is_member is False
    assert response.raw_description is None
    assert response.owner_user_id is None


def test_owner_cannot_be_managed_by_project_membership_operations() -> None:
    policy = ProjectAuthorizationPolicy()

    assert policy.can_manage_target(member("owner"), member("owner")) is False
    assert policy.can_manage_target(member("admin"), member("owner")) is False
    assert policy.can_manage_target(member("founder"), member("owner")) is False


@pytest.mark.asyncio
async def test_project_creation_requires_authentication() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/projects", json={"project_type": "idea", "raw_description": "test"})

    assert response.status_code == 401
