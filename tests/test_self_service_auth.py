import asyncio
import uuid
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.main import app
from app.modules.audit import AuditLog
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity import dependencies as identity_dependencies
from app.modules.identity.models import User, UserIdentity, UserRole
from app.modules.identity.service import IdentityProvisioningService, SelfServiceRoleService


@pytest_asyncio.fixture
async def auth_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable for self-service auth tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def cleanup_identity(factory: async_sessionmaker[AsyncSession], provider: str, subject: str) -> None:
    async with factory() as session:
        user_ids = list(
            (
                await session.execute(
                    select(UserIdentity.user_id).where(
                        UserIdentity.provider == provider,
                        UserIdentity.provider_subject == subject,
                    )
                )
            ).scalars()
        )
        if user_ids:
            await session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(user_ids)))
            await session.execute(delete(User).where(User.id.in_(user_ids)))
            await session.commit()


@pytest.mark.asyncio
async def test_concurrent_first_login_creates_one_user_and_returning_login_reuses_it(auth_factory) -> None:
    marker = uuid.uuid4().hex
    provider = "https://self-service-auth.test/"
    subject = f"concurrent-{marker}"
    claims = {"sub": subject, "email": f"auth-{marker}@example.test", "email_verified": True}

    async def provision():
        async with auth_factory() as session:
            return await IdentityProvisioningService(session).resolve_or_provision(provider=provider, claims=claims)

    try:
        first, second = await asyncio.gather(provision(), provision())
        returning = await provision()
        assert first.user_id == second.user_id == returning.user_id

        async with auth_factory() as session:
            identity_count = await session.scalar(
                select(func.count()).select_from(UserIdentity).where(
                    UserIdentity.provider == provider,
                    UserIdentity.provider_subject == subject,
                )
            )
            user_count = await session.scalar(select(func.count()).select_from(User).where(User.email == claims["email"]))
            audit_count = await session.scalar(
                select(func.count()).select_from(AuditLog).where(
                    AuditLog.actor_user_id == first.user_id,
                    AuditLog.action == "identity.first_login_provisioned",
                )
            )
        assert identity_count == 1
        assert user_count == 1
        assert audit_count == 1
    finally:
        await cleanup_identity(auth_factory, provider, subject)


@pytest.mark.asyncio
async def test_me_provisions_only_from_validated_claims_and_reuses_the_account(auth_factory, monkeypatch) -> None:
    marker = uuid.uuid4().hex
    provider = "https://self-service-auth.test/"
    subject = f"me-{marker}"
    claims = {"sub": subject, "email": f"me-{marker}@example.test"}

    class ValidatedToken:
        settings = SimpleNamespace(oidc_issuer=provider)

        async def validate(self, token: str):
            assert token == "cryptographically-validated-by-test-double"
            return claims

    async def session_override():
        async with auth_factory() as session:
            yield session

    monkeypatch.setattr(identity_dependencies, "get_token_validator", lambda: ValidatedToken())
    app.dependency_overrides[get_session] = session_override
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            first = await client.get("/me", headers={"Authorization": "Bearer cryptographically-validated-by-test-double"})
            returning = await client.get("/me", headers={"Authorization": "Bearer cryptographically-validated-by-test-double"})
        assert first.status_code == 200
        assert returning.status_code == 200
        assert first.json()["id"] == returning.json()["id"]
        assert first.json()["needs_role_onboarding"] is True
    finally:
        app.dependency_overrides.clear()
        await cleanup_identity(auth_factory, provider, subject)


@pytest.mark.asyncio
async def test_role_onboarding_is_multi_role_idempotent_audited_and_blocks_escalation(auth_factory) -> None:
    marker = uuid.uuid4().hex
    provider = "https://self-service-auth.test/"
    subject = f"roles-{marker}"
    claims = {"sub": subject, "email": f"roles-{marker}@example.test"}
    try:
        async with auth_factory() as session:
            principal = await IdentityProvisioningService(session).resolve_or_provision(provider=provider, claims=claims)
        async with auth_factory() as session:
            service = SelfServiceRoleService(session)
            options = await service.options()
            assert [option.code for option in options] == ["entrepreneur", "investor", "researcher"]
            first = await service.replace(principal, ["entrepreneur"], request_id=uuid.uuid4())
            repeated = await service.replace(principal, ["entrepreneur"], request_id=uuid.uuid4())
            multi = await service.replace(principal, ["researcher", "entrepreneur", "investor"], request_id=uuid.uuid4())
            assert first.roles == repeated.roles == ("entrepreneur",)
            assert multi.roles == ("entrepreneur", "investor", "researcher")

        for forbidden in (["admin"], ["research_center"], ["owner"], ["entrepreneur", "admin"]):
            async with auth_factory() as session:
                with pytest.raises(HTTPException) as exc_info:
                    await SelfServiceRoleService(session).replace(principal, forbidden, request_id=uuid.uuid4())
                assert exc_info.value.status_code == 403

        async with auth_factory() as session:
            assignment_count = await session.scalar(
                select(func.count()).select_from(UserRole).where(UserRole.user_id == principal.user_id)
            )
            change_audits = await session.scalar(
                select(func.count()).select_from(AuditLog).where(
                    AuditLog.actor_user_id == principal.user_id,
                    AuditLog.action == "identity.self_service_roles_changed",
                )
            )
        assert assignment_count == 3
        assert change_audits == 2
    finally:
        await cleanup_identity(auth_factory, provider, subject)


@pytest.mark.asyncio
async def test_role_options_and_update_api_use_the_authenticated_users_database_roles(auth_factory) -> None:
    marker = uuid.uuid4().hex
    provider = "https://self-service-auth.test/"
    subject = f"api-{marker}"
    claims = {"sub": subject, "email": f"api-{marker}@example.test"}
    async with auth_factory() as session:
        principal = await IdentityProvisioningService(session).resolve_or_provision(provider=provider, claims=claims)

    async def session_override():
        async with auth_factory() as session:
            yield session

    app.dependency_overrides[get_authenticated_principal] = lambda: principal
    app.dependency_overrides[get_session] = session_override
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            options = await client.get("/me/roles/options", headers={"Authorization": "Bearer opaque-test-value"})
            update = await client.put(
                "/me/roles",
                json={"roles": ["entrepreneur", "researcher"]},
                headers={"Authorization": "Bearer opaque-test-value"},
            )
            denied = await client.put(
                "/me/roles",
                json={"roles": ["admin"]},
                headers={"Authorization": "Bearer opaque-test-value"},
            )
        assert options.status_code == 200
        assert [item["code"] for item in options.json()] == ["entrepreneur", "investor", "researcher"]
        assert update.status_code == 200
        assert update.json()["roles"] == ["entrepreneur", "researcher"]
        assert update.json()["needs_role_onboarding"] is False
        assert denied.status_code == 403
    finally:
        app.dependency_overrides.clear()
        await cleanup_identity(auth_factory, provider, subject)


@pytest.mark.asyncio
async def test_public_browser_config_contains_no_secret() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://regbridge:regbridge@127.0.0.1:55432/regbridge",
        OIDC_ISSUER="https://issuer.example.test/",
        OIDC_AUDIENCE="https://api.example.test/",
        OIDC_CLIENT_ID="regbridge-public-spa",
        OIDC_REDIRECT_URI="http://127.0.0.1:8000/auth/callback/",
        OIDC_POST_LOGOUT_REDIRECT_URI="http://127.0.0.1:8000/auth/login/",
        OIDC_AUTHORIZATION_AUDIENCE="https://api.example.test/",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/auth/config")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["client_id"] == "regbridge-public-spa"
    assert response.json()["authorization_extra_params"] == {"audience": "https://api.example.test/"}
    assert "secret" not in response.text.lower()
