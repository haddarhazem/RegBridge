import asyncio
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.ai.context import AuthorizedContextBuilder, ProjectAuthorizationService
from app.modules.ai.contracts import OrchestrationRequest
from app.modules.audit import AuditLog
from app.modules.documents.models import Document
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.projects.repositories import ProjectContextRepository
from app.modules.projects.service import ProjectService
from app.modules.regulatory.assessment_models import AssessmentInputSnapshot, RegulatoryAssessment
from app.modules.regulatory.roadmap_models import LaunchRoadmap, LaunchRoadmapItem


@pytest_asyncio.fixture
async def lifecycle_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for SCRUM-191 tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="scrum191-test")


async def cleanup(factory, project_id, user_ids):
    async with factory() as session:
        await session.execute(delete(LaunchRoadmapItem).where(LaunchRoadmapItem.roadmap_id.in_(select(LaunchRoadmap.id).where(LaunchRoadmap.project_id == project_id))))
        await session.execute(delete(LaunchRoadmap).where(LaunchRoadmap.project_id == project_id))
        await session.execute(delete(RegulatoryAssessment).where(RegulatoryAssessment.project_id == project_id))
        await session.execute(delete(AssessmentInputSnapshot).where(AssessmentInputSnapshot.project_id == project_id))
        await session.execute(delete(Document).where(Document.project_id == project_id))
        await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
        await session.execute(delete(ProjectFact).where(ProjectFact.project_id == project_id))
        await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_lifecycle_preserves_identity_artifacts_audit_context_and_authorization(lifecycle_factory):
    owner_id, member_id, other_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    owner = principal(owner_id, f"owner-{owner_id}@example.test")
    member = principal(member_id, f"member-{member_id}@example.test")
    other = principal(other_id, f"other-{other_id}@example.test")
    project_id = None
    async with lifecycle_factory() as session:
        session.add_all([User(id=owner_id, email=owner.email), User(id=member_id, email=member.email), User(id=other_id, email=other.email)])
        project = Project(owner_user_id=owner_id, project_type="idea", raw_description="Idea", confirmed_fields={})
        session.add(project)
        await session.flush()
        project_id = project.id
        session.add_all([
            ProjectMember(project_id=project.id, user_id=owner_id, member_role="owner", status="active"),
            ProjectMember(project_id=project.id, user_id=member_id, member_role="member", status="active"),
            ProjectFact(project_id=project.id, domain="technology", value="AI", origin="inferred", status="confirmed", provenance={"source_field": "description"}),
            ProjectFact(project_id=project.id, domain="sector", value="health", origin="inferred", status="pending_confirmation", provenance={"source_field": "description"}),
            ProjectFact(project_id=project.id, domain="data", value="old", origin="inferred", status="deleted", provenance={"source_field": "description"}),
            Document(owner_user_id=owner_id, project_id=project.id, title="Statuts", document_type="legal"),
        ])
        snapshot = AssessmentInputSnapshot(project_id=project.id, facts=[{"domain": "technology", "value": "AI"}], snapshot_hash="a" * 64)
        session.add(snapshot)
        await session.flush()
        assessment = RegulatoryAssessment(project_id=project.id, version=1, snapshot_id=snapshot.id, status="completed", result={}, source_provenance=[], verification_verdict="pass", verification_reasons=[])
        session.add(assessment)
        await session.flush()
        roadmap = LaunchRoadmap(project_id=project.id, regulatory_assessment_id=assessment.id, version=1, purpose="creation")
        session.add(roadmap)
        await session.flush()
        session.add(LaunchRoadmapItem(roadmap_id=roadmap.id, item_type="obligation", title="Create", justification="Assessment", priority_order=1))
        await session.commit()

    try:
        async with lifecycle_factory() as session:
            service = ProjectService(session)
            changed = await service.transition_project(owner, project_id, "startup_in_creation")
            assert changed.id == project_id and changed.project_type == "startup_in_creation"
            same = await service.transition_project(owner, project_id, "startup_in_creation")
            assert same.id == project_id
            current = await session.get(Project, project_id)
            assert current.project_type == "startup_in_creation"
            context = await AuthorizedContextBuilder(ProjectContextRepository(session), ProjectAuthorizationService(ProjectContextRepository(session))).build(OrchestrationRequest(subject_type="project", subject_id=project_id, principal=owner, intent_hint="regulatory"), ["regulatory"])
            assert context.project_type == "startup_in_creation"
            history = await service.lifecycle_history(owner, project_id)
            assert len(history) == 1
            assert history[0].metadata_json == {"from_type": "idea", "to_type": "startup_in_creation"}
            assert (await session.scalar(select(ProjectFact.value).where(ProjectFact.project_id == project_id, ProjectFact.status == "confirmed"))) == "AI"
            assert (await session.scalar(select(Document.project_id).where(Document.project_id == project_id))) == project_id
            assert (await session.scalar(select(AssessmentInputSnapshot.snapshot_hash).where(AssessmentInputSnapshot.project_id == project_id))) == "a" * 64
            assert (await session.scalar(select(LaunchRoadmap.purpose).where(LaunchRoadmap.project_id == project_id))) == "creation"
            await service.transition_project(owner, project_id, "existing_startup")
            assert (await session.get(Project, project_id)).project_type == "existing_startup"
            with pytest.raises(HTTPException):
                await service.transition_project(owner, project_id, "idea")
            with pytest.raises(HTTPException) as denied:
                await service.transition_project(other, project_id, "idea")
            assert denied.value.status_code == 403
            with pytest.raises(HTTPException):
                await service.lifecycle_history(other, project_id)
            with pytest.raises(HTTPException):
                await service.transition_project(member, project_id, "idea")
    finally:
        await cleanup(lifecycle_factory, project_id, [owner_id, member_id, other_id])


@pytest.mark.asyncio
async def test_failed_and_concurrent_transitions_are_safe(lifecycle_factory):
    owner_id, project_id = uuid.uuid4(), None
    owner = principal(owner_id, f"rollback-{owner_id}@example.test")
    async with lifecycle_factory() as session:
        session.add(User(id=owner_id, email=owner.email))
        project = Project(owner_user_id=owner_id, project_type="idea", raw_description="Idea", confirmed_fields={})
        session.add(project)
        await session.flush()
        project_id = project.id
        session.add(ProjectMember(project_id=project.id, user_id=owner_id, member_role="owner", status="active"))
        await session.commit()

    class FailingService(ProjectService):
        async def _audit(self, *args, **kwargs):
            raise RuntimeError("simulated audit failure")

    async def attempt(target):
        async with lifecycle_factory() as session:
            return await ProjectService(session).transition_project(owner, project_id, target)

    try:
        async with lifecycle_factory() as session:
            with pytest.raises(RuntimeError):
                await FailingService(session).transition_project(owner, project_id, "startup_in_creation")
            assert (await session.get(Project, project_id)).project_type == "idea"
            assert not (await session.scalars(select(AuditLog).where(AuditLog.project_id == project_id, AuditLog.action == "project.lifecycle_transition"))).all()
        results = await asyncio.gather(attempt("startup_in_creation"), attempt("startup_in_creation"), return_exceptions=True)
        assert sum(not isinstance(result, Exception) for result in results) == 2
        async with lifecycle_factory() as session:
            assert (await session.get(Project, project_id)).project_type == "startup_in_creation"
            assert len((await session.scalars(select(AuditLog).where(AuditLog.project_id == project_id, AuditLog.action == "project.lifecycle_transition"))).all()) == 1
    finally:
        await cleanup(lifecycle_factory, project_id, [owner_id])
