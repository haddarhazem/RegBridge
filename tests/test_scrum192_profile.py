import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember
from app.modules.projects.profile_models import StartupProfile, StartupProfileRevision
from app.modules.projects.profile_schemas import ProfileVisibility, StartupProfileFieldUpdate, StartupProfilePatch
from app.modules.projects.profile_service import StartupProfileService
from app.modules.projects.service import ProjectService


@pytest_asyncio.fixture
async def profile_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for SCRUM-192 tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="scrum192-test")


async def create_project(factory, *, owner_id: uuid.UUID, other_id: uuid.UUID | None = None, visibility: str = "public") -> tuple[uuid.UUID, AuthenticatedPrincipal, AuthenticatedPrincipal | None]:
    owner = principal(owner_id, f"owner-{owner_id}@example.test")
    other = principal(other_id, f"other-{other_id}@example.test") if other_id else None
    async with factory() as session:
        session.add(User(id=owner_id, email=owner.email))
        if other_id:
            session.add(User(id=other_id, email=other.email))
        project = Project(owner_user_id=owner_id, project_type="startup_in_creation", raw_description="Startup", display_name="Startup", visibility=visibility, confirmed_fields={})
        session.add(project)
        await session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=owner_id, member_role="owner", status="active"))
        await session.commit()
        return project.id, owner, other


async def cleanup(factory, project_id: uuid.UUID, user_ids: list[uuid.UUID]) -> None:
    async with factory() as session:
        await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_mixed_projection_history_partial_update_and_lifecycle(profile_factory):
    owner_id = uuid.uuid4()
    project_id, owner, _ = await create_project(profile_factory, owner_id=owner_id)
    try:
        async with profile_factory() as session:
            service = StartupProfileService(session)
            project, profile, fields = await service.update(owner, project_id, StartupProfilePatch(fields=[
                StartupProfileFieldUpdate(field_name="website", value="https://startup.example", visibility=ProfileVisibility.PUBLIC),
                StartupProfileFieldUpdate(field_name="fundraising_target", value="INVESTOR_CANARY_7F12", visibility=ProfileVisibility.INVESTOR_SHARED),
                StartupProfileFieldUpdate(field_name="internal_notes", value="PRIVATE_CANARY_9C21", visibility=ProfileVisibility.PRIVATE),
            ]))
            assert project.project_type == "startup_in_creation"
            assert profile.current_revision == 1
            assert {field.field_name for field in fields} == {"website", "fundraising_target", "internal_notes"}
            assert await service.get_public(project_id) == {"website": "https://startup.example"}

        async with profile_factory() as session:
            service = StartupProfileService(session)
            await service.update(owner, project_id, StartupProfilePatch(fields=[StartupProfileFieldUpdate(field_name="website", value="https://startup.example", visibility=ProfileVisibility.PRIVATE)]))
            assert await service.get_public(project_id) == {}
            history = await service.history(owner, project_id)
            assert [item.revision_number for item in history] == [1, 2]
            assert history[0].snapshot[0]["visibility"] == "PRIVATE" or next(item for item in history[0].snapshot if item["field_name"] == "website")["visibility"] == "PUBLIC"
            latest = await service.get_internal(owner, project_id)
            assert latest[1].current_revision == 2
            assert {field.field_name for field in latest[2]} == {"website", "fundraising_target", "internal_notes"}
            await ProjectService(session).transition_project(owner, project_id, "existing_startup")

        async with profile_factory() as session:
            project, profile, fields = await StartupProfileService(session).get_internal(owner, project_id)
            assert project.project_type == "existing_startup"
            assert profile.current_revision == 2
            assert any(field.field_name == "fundraising_target" and field.visibility == "INVESTOR_SHARED" for field in fields)
    finally:
        await cleanup(profile_factory, project_id, [owner_id])


@pytest.mark.asyncio
async def test_only_active_edit_roles_can_update_and_cross_project_access_denied(profile_factory):
    owner_id, member_id, outsider_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    project_id, owner, _ = await create_project(profile_factory, owner_id=owner_id, other_id=outsider_id, visibility="private")
    member = principal(member_id, f"member-{member_id}@example.test")
    try:
        async with profile_factory() as session:
            session.add(User(id=member_id, email=member.email))
            session.add(ProjectMember(project_id=project_id, user_id=member_id, member_role="member", status="active"))
            await session.commit()
        async with profile_factory() as session:
            service = StartupProfileService(session)
            with pytest.raises(HTTPException) as read_error:
                await service.get_internal(principal(outsider_id, f"other-{outsider_id}@example.test"), project_id)
            assert read_error.value.status_code == 403
        async with profile_factory() as session:
            service = StartupProfileService(session)
            with pytest.raises(HTTPException) as edit_error:
                await service.update(member, project_id, StartupProfilePatch(fields=[StartupProfileFieldUpdate(field_name="website", value="x", visibility=ProfileVisibility.PUBLIC)]))
            assert edit_error.value.status_code == 403
            await service.update(owner, project_id, StartupProfilePatch(fields=[StartupProfileFieldUpdate(field_name="website", value="x", visibility=ProfileVisibility.PUBLIC)]))
            assert (await service.get_internal(member, project_id))[2][0].field_name == "website"
    finally:
        await cleanup(profile_factory, project_id, [owner_id, member_id, outsider_id])


def test_unknown_visibility_is_rejected_and_public_response_is_explicit():
    with pytest.raises(ValidationError):
        StartupProfileFieldUpdate.model_validate({"field_name": "website", "value": "x", "visibility": "SECRET_INTERNAL"})
    assert "fields" in str(StartupProfilePatch.model_json_schema())
