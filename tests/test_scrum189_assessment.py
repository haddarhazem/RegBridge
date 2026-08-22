import asyncio
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.ai.contracts import AgentResult, OrchestrationResult
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.regulatory.assessment_models import AssessmentInputSnapshot, RegulatoryAssessment
from app.modules.regulatory.assessment_router import response as assessment_response
from app.modules.regulatory.assessment_service import RegulatoryAssessmentService


@pytest_asyncio.fixture
async def assessment_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for SCRUM-189 tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


class FakeOrchestrator:
    def __init__(self, *, verdict="pass", status="succeeded"):
        self.requests = []
        self.verdict = verdict
        self.status = status

    async def run(self, request):
        self.requests.append(request)
        if self.status != "succeeded":
            return OrchestrationResult(request_id=request.request_id, status="failed", selected_capabilities=["regulatory"])
        return OrchestrationResult(
            request_id=request.request_id, status="succeeded", selected_capabilities=["regulatory"],
            results=[AgentResult(
                agent_name="fake-regulatory-agent", capability="regulatory", status="succeeded",
                answer="Réponse réglementaire fondée.", findings=["Une obligation fondée"],
                recommendations=["Une recommandation pratique"], missing_information=["Une incertitude à confirmer"],
                sources=["CNIL"], evidence=[{"point_id": "p-1", "organization": "CNIL", "rank": 1, "retrieval_score": 0.9, "content": "Evidence officielle."}],
                structured_payload={"verification_verdict": self.verdict},
            )],
        )


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="scrum189-test")


async def cleanup(factory, project_id, user_ids):
    async with factory() as session:
        await session.execute(delete(RegulatoryAssessment).where(RegulatoryAssessment.project_id == project_id))
        await session.execute(delete(AssessmentInputSnapshot).where(AssessmentInputSnapshot.project_id == project_id))
        await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
        await session.execute(delete(ProjectFact).where(ProjectFact.project_id == project_id))
        await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_snapshot_filtering_immutability_versioning_structure_sources_and_authorization(assessment_factory):
    user_id, other_id = uuid.uuid4(), uuid.uuid4()
    owner = principal(user_id, f"scrum189-{user_id}@example.test")
    other = principal(other_id, f"scrum189-{other_id}@example.test")
    project_id = None
    fake = FakeOrchestrator()
    async with assessment_factory() as session:
        session.add_all([User(id=user_id, email=owner.email), User(id=other_id, email=other.email)])
        project = Project(owner_user_id=user_id, project_type="idea", raw_description="Projet logiciel", technology="AI", confirmed_fields={"technology": "confirmed"})
        session.add(project)
        await session.flush()
        project_id = project.id
        session.add(ProjectMember(project_id=project.id, user_id=user_id, member_role="owner", status="active"))
        session.add_all([
            ProjectFact(project_id=project.id, domain="sector", value="health", origin="inferred", status="confirmed", provenance={"source_field": "description"}),
            ProjectFact(project_id=project.id, domain="technology", value="pending secret", origin="inferred", status="pending_confirmation", provenance={"source_field": "description"}),
            ProjectFact(project_id=project.id, domain="data", value="old value", origin="inferred", status="deleted", provenance={"source_field": "description"}),
            ProjectFact(project_id=project.id, domain="technology", value="rule-based software", origin="inferred", status="corrected", provenance={"source_field": "description", "original_value": "AI"}),
        ])
        await session.commit()

    class TestService(RegulatoryAssessmentService):
        def _orchestrator(self):
            return fake

    try:
        async with assessment_factory() as session:
            first = await TestService(session).generate(owner, project_id, "Évaluez le projet")
            assert first.version == 1
            snapshot = await session.get(AssessmentInputSnapshot, first.snapshot_id)
            assert {item["value"] for item in snapshot.facts} == {"AI", "health", "rule-based software"}
            assert "pending secret" not in fake.requests[0].question
            assert first.result["obligations"][0]["category"] == "obligation"
            assert first.result["recommendations"][0]["category"] == "recommendation"
            assert first.result["uncertainties"][0]["category"] == "uncertainty"
            assert first.source_provenance[0]["point_id"] == "p-1"

        async with assessment_factory() as session:
            project = await session.get(Project, project_id)
            project.technology = "quantum computing"
            await session.commit()

        async with assessment_factory() as session:
            reloaded = await session.get(RegulatoryAssessment, first.id)
            snapshot = await session.get(AssessmentInputSnapshot, first.snapshot_id)
            assert snapshot.facts[0]["value"] == "AI"
            assert reloaded.result["answer"] == "Réponse réglementaire fondée."
            second = await TestService(session).generate(owner, project_id, "Évaluez le projet")
            assert second.version == 2 and second.snapshot_id != first.snapshot_id

        async with assessment_factory() as session:
            history = list((await session.scalars(select(RegulatoryAssessment).where(RegulatoryAssessment.project_id == project_id).order_by(RegulatoryAssessment.version))).all())
            assert [item.version for item in history] == [1, 2]
            assert (await TestService(session).latest(owner, project_id)).version == 2
            public = assessment_response(history[0])
            assert public.result.obligations[0].source_refs == ["CNIL"]
            assert "p-1" not in str(public.model_dump())
            operations = [
                lambda: TestService(session).generate(other, project_id, "Évaluez"),
                lambda: TestService(session).latest(other, project_id),
                lambda: TestService(session).list_versions(other, project_id),
                lambda: TestService(session).get_version(other, project_id, 1),
            ]
            for operation in operations:
                with pytest.raises(HTTPException) as denied:
                    await operation()
                assert denied.value.status_code == 404
    finally:
        await cleanup(assessment_factory, project_id, [user_id, other_id])


@pytest.mark.asyncio
async def test_concurrent_generation_serializes_project_versions(assessment_factory):
    user_id, project_id = uuid.uuid4(), None
    owner = principal(user_id, f"scrum189-race-{user_id}@example.test")
    fake = FakeOrchestrator()
    async with assessment_factory() as session:
        session.add(User(id=user_id, email=owner.email))
        project = Project(owner_user_id=user_id, project_type="idea", raw_description="Projet concurrent", technology="AI", confirmed_fields={"technology": "confirmed"})
        session.add(project)
        await session.flush()
        project_id = project.id
        session.add(ProjectMember(project_id=project.id, user_id=user_id, member_role="owner", status="active"))
        await session.commit()

    class TestService(RegulatoryAssessmentService):
        def _orchestrator(self):
            return fake

    async def generate_one():
        async with assessment_factory() as session:
            return await TestService(session).generate(owner, project_id, "Évaluez")

    try:
        first, second = await asyncio.gather(generate_one(), generate_one())
        assert {first.version, second.version} == {1, 2}
    finally:
        await cleanup(assessment_factory, project_id, [user_id])


@pytest.mark.asyncio
async def test_blocked_warning_and_generation_failure_are_explicit_safe_states(assessment_factory):
    user_id, project_id = uuid.uuid4(), None
    owner = principal(user_id, f"scrum189-failure-{user_id}@example.test")
    async with assessment_factory() as session:
        session.add(User(id=user_id, email=owner.email))
        project = Project(owner_user_id=user_id, project_type="idea", raw_description="Projet contrôlé", technology="AI", confirmed_fields={"technology": "confirmed"})
        session.add(project)
        await session.flush()
        project_id = project.id
        session.add(ProjectMember(project_id=project.id, user_id=user_id, member_role="owner", status="active"))
        await session.commit()

    class TestService(RegulatoryAssessmentService):
        def __init__(self, session, fake):
            super().__init__(session)
            self.fake = fake

        def _orchestrator(self):
            return self.fake

    try:
        async with assessment_factory() as session:
            blocked = await TestService(session, FakeOrchestrator(verdict="block")).generate(owner, project_id, "Évaluez")
            assert blocked.status == "blocked"
            assert blocked.verification_verdict == "block"
            warned = await TestService(session, FakeOrchestrator(verdict="pass_with_warnings")).generate(owner, project_id, "Évaluez")
            assert warned.status == "completed"
            assert warned.verification_verdict == "pass_with_warnings"
            failed = await TestService(session, FakeOrchestrator(status="failed")).generate(owner, project_id, "Évaluez")
            assert failed.status == "failed"
            statuses = list((await session.scalars(select(RegulatoryAssessment.status).where(RegulatoryAssessment.project_id == project_id))).all())
            assert "completed" in statuses
            assert statuses.count("completed") == 1
            assert "blocked" in statuses and "failed" in statuses
    finally:
        await cleanup(assessment_factory, project_id, [user_id])
