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
from app.modules.regulatory.roadmap_contracts import RoadmapItemStatusUpdate
from app.modules.regulatory.roadmap_generation import generate_launch_items
from app.modules.regulatory.roadmap_models import LaunchRoadmap, LaunchRoadmapItem
from app.modules.regulatory.roadmap_router import update_roadmap_item
from app.modules.regulatory.roadmap_service import LaunchRoadmapService


@pytest_asyncio.fixture
async def roadmap_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for roadmap tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="roadmap-test")


def assessment_result(statement: str = "Documenter les traitements de données personnelles") -> dict:
    return {
        "answer": "Réponse vérifiée",
        "obligations": [{"conclusion_id": "o-1", "statement": statement, "category": "obligation", "source_refs": ["p-1"]}],
        "recommendations": [{"conclusion_id": "r-1", "statement": "Préparer une procédure réglementaire vérifiée", "category": "recommendation", "source_refs": ["p-1"]}],
        "uncertainties": [{"conclusion_id": "u-1", "statement": "Conclusion non prouvée", "category": "uncertainty", "source_refs": []}],
        "sources": ["Autorité synthétique"],
    }


def test_launch_generation_personalizes_only_from_confirmed_context() -> None:
    minimal = generate_launch_items({"activity": "Conseil", "sector": "Services"}, "startup_in_creation")
    assert len(minimal) >= 9
    assert {item["item_type"] for item in minimal}.isdisjoint({"privacy", "security", "hr"})
    assert all(item["source_conclusion_refs"][0].startswith("BASELINE:") for item in minimal)

    tailored = generate_launch_items({
        "activity": "Plateforme B2B pour PME avec objets connectés",
        "sector": "EnergyTech",
        "technology": "SaaS cloud, IA/ML et IoT",
        "data": "Données personnelles clients et données énergétiques",
        "market": "PME B2B en France",
        "location": "France",
    }, "startup_in_creation")
    categories = {item["item_type"] for item in tailored}
    assert {"privacy", "security", "regulatory", "contracts"} <= categories
    assert "hr" not in categories
    assert any(ref.startswith("PROJECT_CONTEXT:") for item in tailored for ref in item["source_conclusion_refs"])


def test_regulatory_enrichment_excludes_uncertainties_and_deduplicates() -> None:
    baseline_title = "Confirmer la structure juridique adaptée au projet"
    items = generate_launch_items(
        {"activity": "Conseil", "sector": "Services"},
        "startup_in_creation",
        assessment_result(baseline_title),
    )
    assert sum(item["title"] == baseline_title for item in items) == 1
    duplicate = next(item for item in items if item["title"] == baseline_title)
    assert any(ref == "REGULATORY_ASSESSMENT:o-1" for ref in duplicate["source_conclusion_refs"])
    assert any(item["title"] == "Préparer une procédure réglementaire vérifiée" for item in items)
    assert not any(item["title"] == "Conclusion non prouvée" for item in items)


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


@pytest.mark.asyncio
async def test_roadmap_without_empty_failed_and_usable_assessment(roadmap_factory):
    user_id, other_id = uuid.uuid4(), uuid.uuid4()
    owner = principal(user_id, f"roadmap-{user_id}@example.test")
    other = principal(other_id, f"roadmap-{other_id}@example.test")
    project_id = None
    async with roadmap_factory() as session:
        session.add_all([User(id=user_id, email=owner.email), User(id=other_id, email=other.email)])
        project = Project(
            owner_user_id=user_id,
            project_type="startup_in_creation",
            raw_description="Texte brut non utilisé",
            activity="Plateforme SaaS",
            sector="EnergyTech",
            technology="IA/ML, IoT et cloud",
            data_context="Données personnelles clients et données énergétiques",
            target_market="PME B2B en France",
            location="France",
            confirmed_fields={field: "confirmed" for field in ("activity", "sector", "technology", "data", "market", "location")},
        )
        session.add(project)
        await session.flush()
        project_id = project.id
        session.add(ProjectMember(project_id=project.id, user_id=user_id, member_role="owner", status="active"))
        await session.commit()

    try:
        async with roadmap_factory() as session:
            service = LaunchRoadmapService(session)
            no_assessment = await service.generate(owner, project_id)
            no_assessment_items = await service._items(no_assessment.id)
            assert no_assessment.version == 1 and no_assessment.regulatory_assessment_id is None
            assert {"privacy", "security", "regulatory", "launch"} <= {item.item_type for item in no_assessment_items}
            assert all("Conclusion non prouvée" != item.title for item in no_assessment_items)

        async with roadmap_factory() as session:
            snapshot = AssessmentInputSnapshot(project_id=project_id, facts=[], snapshot_hash="0" * 64)
            session.add(snapshot)
            await session.flush()
            empty = RegulatoryAssessment(project_id=project_id, version=1, snapshot_id=snapshot.id, status="completed", result={"obligations": [], "recommendations": [], "uncertainties": []}, source_provenance=[], verification_verdict="pass", verification_reasons=[])
            failed = RegulatoryAssessment(project_id=project_id, version=2, snapshot_id=snapshot.id, status="failed", result=assessment_result(), source_provenance=[], verification_verdict="block", verification_reasons=["failed"])
            usable = RegulatoryAssessment(project_id=project_id, version=3, snapshot_id=snapshot.id, status="completed", result=assessment_result(), source_provenance=[{"point_id": "p-1", "organization": "Autorité synthétique"}], verification_verdict="pass", verification_reasons=[])
            session.add_all([empty, failed, usable])
            await session.flush()
            empty_id, failed_id, usable_id = empty.id, failed.id, usable.id
            await session.commit()

        async with roadmap_factory() as session:
            service = LaunchRoadmapService(session)
            empty_roadmap = await service.generate(owner, project_id, empty_id)
            failed_roadmap = await service.generate(owner, project_id, failed_id)
            enriched = await service.generate(owner, project_id, usable_id)
            enriched_items = await service._items(enriched.id)
            assert empty_roadmap.regulatory_assessment_id is None
            assert failed_roadmap.regulatory_assessment_id is None
            assert enriched.regulatory_assessment_id == usable_id
            assert [empty_roadmap.version, failed_roadmap.version, enriched.version] == [2, 3, 4]
            assert any(item.title == "Préparer une procédure réglementaire vérifiée" for item in enriched_items)
            assert not any(item.title == "Conclusion non prouvée" for item in enriched_items)
            await service.update_item(owner, project_id, 4, enriched_items[0].id, "in_progress")
            updated = await update_roadmap_item(project_id, 4, enriched_items[0].id, RoadmapItemStatusUpdate(status="completed"), owner, session)
            assert updated.status == "completed"

        async with roadmap_factory() as session:
            service = LaunchRoadmapService(session)
            reloaded, reloaded_items = await service.get_version(owner, project_id, 4)
            assert reloaded_items[0].status == "completed"
            first_item_id = reloaded_items[0].id
            assert [roadmap.version for roadmap, _ in await service.list_versions(owner, project_id)] == [1, 2, 3, 4]
            with pytest.raises(HTTPException) as denied:
                await service.generate(other, project_id)
            assert denied.value.status_code == 404
            with pytest.raises(HTTPException):
                await service.update_item(other, project_id, 4, first_item_id, "skipped")
    finally:
        await cleanup(roadmap_factory, project_id, [user_id, other_id])


@pytest.mark.asyncio
async def test_roadmap_reports_missing_project_prerequisites(roadmap_factory):
    user_id = uuid.uuid4()
    actor = principal(user_id, f"roadmap-missing-{user_id}@example.test")
    project_id = None
    async with roadmap_factory() as session:
        session.add(User(id=user_id, email=actor.email))
        project = Project(owner_user_id=user_id, project_type="idea", raw_description="Unconfirmed", confirmed_fields={})
        session.add(project)
        await session.flush()
        project_id = project.id
        session.add(ProjectMember(project_id=project.id, user_id=user_id, member_role="owner", status="active"))
        await session.commit()
    try:
        async with roadmap_factory() as session:
            with pytest.raises(HTTPException, match="au moins deux informations") as error:
                await LaunchRoadmapService(session).generate(actor, project_id)
            assert error.value.status_code == 409
    finally:
        await cleanup(roadmap_factory, project_id, [user_id])
