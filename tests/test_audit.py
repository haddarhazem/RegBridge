import uuid

from app.modules.documents.service import DocumentService
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.service import ProjectService


class CaptureSession:
    def __init__(self) -> None:
        self.items = []

    def add(self, item) -> None:
        self.items.append(item)


def principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=uuid.uuid4(), email="audit@example.test", roles=("entrepreneur",), provider="issuer.example.test")


def test_project_audit_contains_actor_action_resource_project_and_metadata() -> None:
    session = CaptureSession()
    project_id = uuid.uuid4()
    resource_id = uuid.uuid4()
    service = ProjectService(session)  # type: ignore[arg-type]
    actor = principal()

    import asyncio

    asyncio.run(service._audit(actor, "project.member.role_changed", project_id, resource_id, "project_member", {"old_role": "member", "new_role": "viewer"}))
    audit = session.items[0]

    assert audit.actor_user_id == actor.user_id
    assert audit.action == "project.member.role_changed"
    assert audit.resource_type == "project_member"
    assert audit.resource_id == resource_id
    assert audit.project_id == project_id
    assert audit.metadata_json == {"old_role": "member", "new_role": "viewer"}
    assert audit.created_at is None


def test_document_audit_contains_document_resource_and_safe_metadata() -> None:
    session = CaptureSession()
    document_id = uuid.uuid4()
    project_id = uuid.uuid4()
    service = DocumentService(session, storage=object(), scanner=object())  # type: ignore[arg-type]
    actor = principal()

    import asyncio

    asyncio.run(service._audit(actor, "document.quarantined", document_id, {"version_id": str(uuid.uuid4())}, project_id))
    audit = session.items[0]

    assert audit.actor_user_id == actor.user_id
    assert audit.action == "document.quarantined"
    assert audit.resource_type == "document"
    assert audit.resource_id == document_id
    assert audit.project_id == project_id
    assert "token" not in audit.metadata_json
    assert "content" not in audit.metadata_json
