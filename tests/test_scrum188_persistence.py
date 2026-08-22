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
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.projects.repositories import ProjectContextRepository
from app.modules.projects.service import ProjectService


@pytest_asyncio.fixture
async def facts_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for SCRUM-188 persistence tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="scrum188-test")


@pytest.mark.asyncio
async def test_fact_inference_confirmation_correction_context_and_cross_user_denial(facts_factory: async_sessionmaker[AsyncSession]):
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    project_id: uuid.UUID | None = None
    email_a = f"scrum188-a-{user_a}@example.test"
    email_b = f"scrum188-b-{user_b}@example.test"
    owner = principal(user_a, email_a)
    other = principal(user_b, email_b)

    async with facts_factory() as session:
        session.add_all([User(id=user_a, email=email_a), User(id=user_b, email=email_b)])
        project = Project(owner_user_id=user_a, project_type="idea", raw_description="Nous créons une application SaaS qui traite les données personnelles de clients en France.", technology="rule-based software", target_market=None, confirmed_fields={}, onboarding_status="in_progress")
        session.add(project)
        await session.flush()
        project_id = project.id
        session.add(ProjectMember(project_id=project.id, user_id=user_a, member_role="owner", status="active"))
        await session.commit()

    try:
        async with facts_factory() as session:
            inferred = await ProjectService(session).infer_facts(owner, project_id)
            assert inferred
            assert all(fact.status == "pending_confirmation" for fact in inferred)
            fact_id = inferred[0].id

        async with facts_factory() as session:
            reloaded = list((await session.scalars(select(ProjectFact).where(ProjectFact.id == fact_id))).all())
            assert reloaded[0].provenance["source_field"] == "description"
            with pytest.raises(HTTPException) as denied_read:
                await ProjectService(session).list_facts(other, project_id)
            assert denied_read.value.status_code == 403

        async with facts_factory() as session:
            confirmed = await ProjectService(session).confirm_fact(owner, project_id, fact_id)
            assert confirmed.status == "confirmed"

        async with facts_factory() as session:
            corrected = await ProjectService(session).correct_fact(owner, project_id, fact_id, "rule-based software")
            assert corrected.status == "corrected"
            assert corrected.origin == "inferred"
            assert corrected.provenance["original_value"]

        async with facts_factory() as session:
            reloaded = await session.get(ProjectFact, fact_id)
            assert reloaded.value == "rule-based software"
            context = await AuthorizedContextBuilder(
                ProjectContextRepository(session),
                ProjectAuthorizationService(ProjectContextRepository(session)),
            ).build(OrchestrationRequest(subject_type="project", subject_id=project_id, principal=owner, intent_hint="regulatory"), ["regulatory"])
            assert any(fact["value"] == "rule-based software" and fact["status"] == "corrected" for fact in context.facts)
            assert not any(fact["value"] == "AI" and fact["status"] == "pending_confirmation" for fact in context.facts)
            assert context.technology == "rule-based software"

            pending = (await ProjectService(session).infer_facts(owner, project_id))[0]
            assert pending.status == "pending_confirmation"
            rejected = await ProjectService(session).reject_fact(owner, project_id, pending.id)
            assert rejected.status == "deleted"

            context_after_reject = await AuthorizedContextBuilder(
                ProjectContextRepository(session),
                ProjectAuthorizationService(ProjectContextRepository(session)),
            ).build(OrchestrationRequest(subject_type="project", subject_id=project_id, principal=owner, intent_hint="regulatory"), ["regulatory"])
            assert not any(fact["status"] == "deleted" for fact in context_after_reject.facts)

            with pytest.raises(HTTPException) as denied_update:
                await ProjectService(session).confirm_fact(other, project_id, fact_id)
            assert denied_update.value.status_code == 403

            with pytest.raises(HTTPException) as denied_correct:
                await ProjectService(session).correct_fact(other, project_id, fact_id, "unauthorized")
            assert denied_correct.value.status_code == 403

            with pytest.raises(HTTPException) as denied_delete:
                await ProjectService(session).reject_fact(other, project_id, fact_id)
            assert denied_delete.value.status_code == 403
    finally:
        async with facts_factory() as session:
            await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
            await session.execute(delete(ProjectFact).where(ProjectFact.project_id == project_id))
            await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
            await session.execute(delete(Project).where(Project.id == project_id))
            await session.execute(delete(User).where(User.id.in_([user_a, user_b])))
            await session.commit()
