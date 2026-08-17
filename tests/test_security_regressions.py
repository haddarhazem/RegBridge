import uuid
from types import SimpleNamespace

import pytest

from app.modules.documents.authorization import DocumentAuthorizationPolicy
from app.modules.projects.authorization import ProjectAuthorizationPolicy
from app.modules.projects.router import project_response
from app.modules.documents.service import build_storage_key


def membership(role: str, state: str = "active") -> SimpleNamespace:
    return SimpleNamespace(member_role=role, status=state)


def project(state: str = "private") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        project_type="idea",
        display_name="private project",
        visibility=state,
        raw_description="sensitive project details",
        user_goal=None,
        current_progress=None,
        country_code="FR",
        target_market="France",
        language="fr",
        owner_user_id=uuid.uuid4(),
    )


def test_project_idor_private_project_denies_unrelated_user() -> None:
    policy = ProjectAuthorizationPolicy()

    assert policy.can_view(project("private"), None) is False


@pytest.mark.parametrize("state", ["invited", "revoked"])
def test_project_inactive_membership_has_no_access(state: str) -> None:
    assert ProjectAuthorizationPolicy().can_view(project("private"), membership("member", state)) is False


def test_project_viewer_is_read_only_and_member_cannot_manage_members() -> None:
    policy = ProjectAuthorizationPolicy()

    assert policy.can_view(project(), membership("viewer")) is True
    assert policy.can_edit(membership("viewer")) is False
    assert policy.can_manage_members(membership("viewer")) is False
    assert policy.can_manage_members(membership("member")) is False


def test_project_owner_protection_rejects_membership_management_target() -> None:
    policy = ProjectAuthorizationPolicy()

    assert policy.can_manage_target(membership("admin"), membership("owner")) is False
    assert policy.can_manage_target(membership("founder"), membership("owner")) is False


def test_public_project_non_member_response_does_not_expose_private_fields() -> None:
    response = project_response(project("public"), None)

    assert response.raw_description is None
    assert response.owner_user_id is None


def test_document_idor_and_shared_visibility_fail_closed() -> None:
    policy = DocumentAuthorizationPolicy()
    member = membership("member")

    assert policy.can_read("private", "confidential", member, uuid.uuid4(), uuid.uuid4()) is False
    assert policy.can_read("shared", "confidential", member, uuid.uuid4(), uuid.uuid4()) is False


def test_document_viewer_cannot_upload_or_create_versions() -> None:
    assert DocumentAuthorizationPolicy().can_upload(membership("viewer")) is False


def test_document_revoked_and_invited_members_cannot_read() -> None:
    policy = DocumentAuthorizationPolicy()
    owner_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    assert policy.can_read("project_members", "confidential", membership("member", "revoked"), owner_id, actor_id) is False
    assert policy.can_read("project_members", "confidential", membership("member", "invited"), owner_id, actor_id) is False


def test_document_storage_key_cannot_be_used_as_an_authorization_input() -> None:
    key = build_storage_key(uuid.uuid4(), uuid.uuid4())

    assert key.startswith("documents/")
    assert "../" not in key
    assert "secret" not in key
