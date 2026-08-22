import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember
from app.modules.regulatory.assessment_models import AssessmentInputSnapshot, RegulatoryAssessment
from app.modules.regulatory.roadmap_generation import generate_typed_items
from app.modules.regulatory.roadmap_models import LaunchRoadmap, LaunchRoadmapItem
from app.modules.regulatory.roadmap_service import LaunchRoadmapService


@pytest_asyncio.fixture
async def roadmap_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for SCRUM-190 tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="scrum190-test")


def result(*, verdict="pass"):
    return {
        "answer": "Réponse vérifiée",
        "obligations": [{"conclusion_id": "o-1", "statement": "Faire la formalité", "category": "obligation", "source_refs": ["p-1"]}],
        "recommendations": [{"conclusion_id": "r-1", "statement": "Préparer les procédures", "category": "recommendation", "source_refs": ["p-1"]}],
        "uncertainties": [{"conclusion_id": "u-1", "statement": "Confirmer le périmètre", "category": "uncertainty", "source_refs": []}],
        "sources": ["CNIL"],
    }, verdict


async def cleanup(factory, project_id, user_ids):
    async with factory() as session:
        await session.execute(delete(LaunchRoadmapItem).where(LaunchRoadmapItem.roadmap_id.in_(select(LaunchRoadmap.id).where(LaunchRoadmap.project_id == project_id))))
        await session.execute(delete(LaunchRoadmap).where(LaunchRoadmap.project_id == project_id))
        await session.execute(delete(RegulatoryAssessment).where(RegulatoryAssessment.project_id == project_id))
        await session.execute(delete(AssessmentInputSnapshot).where(AssessmentInputSnapshot.project_id == project_id))
        await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
        await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


def test_typed_generation_does_not_invent_steps_or_reclassify():
    items = generate_typed_items(result()[0])
    assert [item["item_type"] for item in items] == ["obligation", "recommendation", "uncertainty"]
    assert all(item["source_conclusion_refs"] for item in items[:2])


@pytest.mark.asyncio
async def test_roadmap_history_progress_provenance_and_cross_user_authorization(roadmap_factory):
    user_id, other_id, project_id = uuid.uuid4(), uuid.uuid4(), None
    owner = principal(user_id, f"scrum190-{user_id}@example.test")
    other = principal(other_id, f"scrum190-{other_id}@example.test")
    assessment_id = None
    async with roadmap_factory() as session:
        session.add_all([User(id=user_id, email=owner.email), User(id=other_id, email=other.email)])
        project = Project(owner_user_id=user_id, project_type="idea", raw_description="Projet", confirmed_fields={})
        session.add(project)
        await session.flush()
        project_id = project.id
        session.add(ProjectMember(project_id=project.id, user_id=user_id, member_role="owner", status="active"))
        snapshot = AssessmentInputSnapshot(project_id=project.id, facts=[], snapshot_hash="0" * 64)
        session.add(snapshot)
        await session.flush()
        assessment = RegulatoryAssessment(project_id=project.id, version=1, snapshot_id=snapshot.id, status="completed", result=result()[0], source_provenance=[{"point_id": "p-1", "organization": "CNIL"}], verification_verdict="pass", verification_reasons=[])
        session.add(assessment)
        await session.flush()
        assessment_id = assessment.id
        await session.commit()

    try:
        async with roadmap_factory() as session:
            service = LaunchRoadmapService(session)
            roadmap = await service.generate(owner, project_id, assessment_id)
            items = await service._items(roadmap.id)
            assert roadmap.version == 1
            assert roadmap.regulatory_assessment_id == assessment_id
            assert [item.item_type for item in items] == ["obligation", "recommendation", "uncertainty"]
            await service.update_item(owner, project_id, 1, items[0].id, "in_progress")
            await service.update_item(owner, project_id, 1, items[0].id, "completed")

        async with roadmap_factory() as session:
            reloaded, reloaded_items = await LaunchRoadmapService(session).get_version(owner, project_id, 1)
            assert reloaded_items[0].status == "completed"
            snapshot_two = AssessmentInputSnapshot(project_id=project_id, facts=[], snapshot_hash="1" * 64)
            session.add(snapshot_two)
            await session.flush()
            assessment_two = RegulatoryAssessment(project_id=project_id, version=2, snapshot_id=snapshot_two.id, status="completed", result=result()[0], source_provenance=[{"point_id": "p-1", "organization": "CNIL"}], verification_verdict="pass", verification_reasons=[])
            session.add(assessment_two)
            await session.flush()
            roadmap_two = await LaunchRoadmapService(session).generate(owner, project_id, assessment_two.id)
            assert roadmap_two.version == 2 and roadmap_two.id != reloaded.id
            history = await LaunchRoadmapService(session).list_versions(owner, project_id)
            assert [item.version for item, _ in history] == [1, 2]
            latest, _ = await LaunchRoadmapService(session).latest(owner, project_id)
            assert latest.version == 2
            blocked_snapshot = AssessmentInputSnapshot(project_id=project_id, facts=[], snapshot_hash="2" * 64)
            session.add(blocked_snapshot)
            await session.flush()
            blocked_assessment = RegulatoryAssessment(project_id=project_id, version=3, snapshot_id=blocked_snapshot.id, status="blocked", result=result()[0], source_provenance=[], verification_verdict="block", verification_reasons=["unsupported"])
            session.add(blocked_assessment)
            await session.flush()
            with pytest.raises(HTTPException) as blocked_assessment_error:
                await LaunchRoadmapService(session).generate(owner, project_id, blocked_assessment.id)
            assert blocked_assessment_error.value.status_code == 409
            with pytest.raises(HTTPException) as blocked:
                await LaunchRoadmapService(session).generate(other, project_id, assessment_id)
            assert blocked.value.status_code == 404
            with pytest.raises(HTTPException):
                await LaunchRoadmapService(session).latest(other, project_id)
            with pytest.raises(HTTPException):
                await LaunchRoadmapService(session).list_versions(other, project_id)
            with pytest.raises(HTTPException):
                await LaunchRoadmapService(session).update_item(other, project_id, 1, reloaded_items[0].id, "skipped")
    finally:
        await cleanup(roadmap_factory, project_id, [user_id, other_id])
