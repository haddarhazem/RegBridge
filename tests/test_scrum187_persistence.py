import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember
from app.modules.projects.onboarding import next_questions
from app.modules.projects.repositories import ProjectContextRepository
from app.modules.projects.schemas import IdeaOnboardingUpdate, IdeaProjectCreate
from app.modules.projects.service import ProjectService


@pytest_asyncio.fixture
async def persistence_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for SCRUM-187 persistence tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="scrum187-persistence-test")


@pytest.mark.asyncio
async def test_scrum187_persistence_round_trip_and_cross_user_denial(
    persistence_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    project_id: uuid.UUID | None = None
    email_a = f"scrum187-a-{user_a_id}@example.test"
    email_b = f"scrum187-b-{user_b_id}@example.test"
    data_context = (
        "Le projet prévoit de collecter et traiter principalement des données énergétiques et techniques : "
        "consommation d’électricité et de gaz, données issues de compteurs intelligents et de capteurs IoT, "
        "informations sur les bâtiments et équipements, historiques de consommation et factures énergétiques. "
        "Il traitera également des données personnelles limitées pour la gestion des comptes utilisateurs, comme "
        "le nom, l’adresse e-mail professionnelle, le rôle dans l’entreprise et les journaux de connexion. "
        "Aucune donnée de santé, biométrique ou financière sensible n’est prévue."
    )

    async with persistence_factory() as session:
        session.add_all([User(id=user_a_id, email=email_a), User(id=user_b_id, email=email_b)])
        await session.commit()

    try:
        async with persistence_factory() as session:
            owner = principal(user_a_id, email_a)
            project = await ProjectService(session).create_idea(owner, IdeaProjectCreate(display_name="Persistent idea"))
            project_id = project.id
            await ProjectService(session).update_onboarding(
                owner,
                project.id,
                IdeaOnboardingUpdate(
                    activity="Local service",
                    sector="Services",
                    data=data_context,
                    confirm=["activity", "sector", "data"],
                ),
            )

        async with persistence_factory() as session:
            owner = principal(user_a_id, email_a)
            project = await ProjectService(session).get_idea_for_user(owner, project_id)
            assert project.activity == "Local service"
            assert project.sector == "Services"
            assert project.data_context == data_context
            assert project.confirmed_fields == {
                "activity": "confirmed",
                "sector": "confirmed",
                "data": "confirmed",
            }

        async with persistence_factory() as session:
            owner = principal(user_a_id, email_a)
            await ProjectService(session).update_onboarding(
                owner,
                project_id,
                IdeaOnboardingUpdate(target_market="France", confirm=["market"]),
            )

        async with persistence_factory() as session:
            owner = principal(user_a_id, email_a)
            project = await ProjectService(session).get_idea_for_user(owner, project_id)
            assert project.activity == "Local service"
            assert project.sector == "Services"
            assert project.target_market == "France"
            assert project.confirmed_fields == {
                "activity": "confirmed",
                "sector": "confirmed",
                "data": "confirmed",
                "market": "confirmed",
            }
            next_fields = {question.field for question in next_questions(project)}
            assert "activity" not in next_fields
            assert "sector" not in next_fields
            assert "data" not in next_fields
            assert "market" not in next_fields

            other = principal(user_b_id, email_b)
            with pytest.raises(Exception) as read_error:
                await ProjectService(session).get_idea_for_user(other, project_id)
            assert getattr(read_error.value, "status_code", None) == 404
            await session.rollback()

            with pytest.raises(Exception) as update_error:
                await ProjectService(session).update_onboarding(
                    other, project_id, IdeaOnboardingUpdate(activity="unauthorized")
                )
            assert getattr(update_error.value, "status_code", None) in {403, 404}
            await session.rollback()
    finally:
        if project_id is not None:
            async with persistence_factory() as session:
                await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
                await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
                await session.execute(delete(Project).where(Project.id == project_id))
                await session.execute(delete(User).where(User.id.in_([user_a_id, user_b_id])))
                await session.commit()


@pytest.mark.asyncio
async def test_project_context_projection_excludes_unconfirmed_declared_fields(
    persistence_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = uuid.uuid4()
    project_id: uuid.UUID | None = None
    email = f"scrum187-context-{user_id}@example.test"

    async with persistence_factory() as session:
        session.add(User(id=user_id, email=email))
        project = Project(
            owner_user_id=user_id,
            project_type="idea",
            raw_description="A synthetic project",
            activity="Confirmed activity",
            sector="Unconfirmed sector",
            technology="Unconfirmed technology",
            data_context="Unconfirmed data",
            target_market="Unconfirmed market",
            location="Unconfirmed location",
            confirmed_fields={"activity": "confirmed"},
        )
        session.add(project)
        await session.flush()
        project_id = project.id
        session.add(ProjectMember(project_id=project.id, user_id=user_id, member_role="owner", status="active"))
        await session.commit()

    try:
        async with persistence_factory() as session:
            projection = await ProjectContextRepository(session).load_minimal_projection(project_id)
            assert projection is not None
            assert projection.activity == "Confirmed activity"
            assert projection.sector is None
            assert projection.technology is None
            assert projection.data_context is None
            assert projection.target_market is None
            assert projection.location is None
    finally:
        async with persistence_factory() as session:
            await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
            await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
            await session.execute(delete(Project).where(Project.id == project_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
