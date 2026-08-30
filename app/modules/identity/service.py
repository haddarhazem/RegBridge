import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import AuditLog
from app.modules.identity.models import Role, User, UserIdentity, UserRole
from app.modules.identity.schemas import AuthenticatedPrincipal, MeResponse, RoleOptionResponse


SELF_SERVICE_ROLE_DEFINITIONS: dict[str, tuple[str, str]] = {
    "entrepreneur": ("Entrepreneur / Startup", "Créer ou gérer un projet"),
    "investor": ("Investisseur", "Découvrir des startups et gérer une thèse"),
    "researcher": ("Chercheur", "Déposer une recherche et collaborer"),
}
SELF_SERVICE_ROLE_CODES = frozenset(SELF_SERVICE_ROLE_DEFINITIONS)


class IdentityProvisioningService:
    """Resolve trusted OIDC identities and provision a minimal account once."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve_or_provision(
        self,
        *,
        provider: str,
        claims: Mapping[str, Any],
        request_id: uuid.UUID | None = None,
    ) -> AuthenticatedPrincipal:
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated identity is invalid")
        if not provider or len(provider) > 80:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication service unavailable")

        resolved = await self._find(provider, subject)
        if resolved is None:
            email = self._provisioning_email(claims)
            user = User(
                id=uuid.uuid4(),
                email=email,
                first_name=self._optional_claim(claims, "given_name", 120),
                last_name=self._optional_claim(claims, "family_name", 120),
            )
            identity = UserIdentity(
                id=uuid.uuid4(),
                user_id=user.id,
                provider=provider,
                provider_subject=subject,
                email_at_provider=email,
                email_verified_at=datetime.now(timezone.utc) if claims.get("email_verified") is True else None,
            )
            self.session.add_all([user, identity])
            try:
                await self.session.flush()
                self.session.add(
                    AuditLog(
                        actor_user_id=user.id,
                        actor_type="user",
                        action="identity.first_login_provisioned",
                        resource_type="user",
                        resource_id=user.id,
                        request_id=request_id,
                        metadata_json={"provider": provider},
                    )
                )
                await self.session.commit()
                resolved = (identity, user)
            except IntegrityError:
                await self.session.rollback()
                resolved = await self._find(provider, subject)
                if resolved is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Authenticated identity requires account linking",
                    ) from None

        identity, user = resolved
        if user.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is unavailable")
        return AuthenticatedPrincipal(
            user_id=user.id,
            email=user.email,
            roles=await self._role_codes(user.id),
            provider=identity.provider,
        )

    async def _find(self, provider: str, subject: str) -> tuple[UserIdentity, User] | None:
        result = await self.session.execute(
            select(UserIdentity, User).join(User, User.id == UserIdentity.user_id).where(
                UserIdentity.provider == provider,
                UserIdentity.provider_subject == subject,
            )
        )
        return result.one_or_none()

    async def _role_codes(self, user_id: uuid.UUID) -> tuple[str, ...]:
        result = await self.session.execute(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.code)
        )
        return tuple(result.scalars().all())

    @staticmethod
    def _provisioning_email(claims: Mapping[str, Any]) -> str:
        value = claims.get("email")
        if not isinstance(value, str):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Identity provider did not supply an email for account provisioning",
            )
        email = value.strip().lower()
        if not email or len(email) > 320 or "@" not in email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Identity provider supplied an invalid email for account provisioning",
            )
        return email

    @staticmethod
    def _optional_claim(claims: Mapping[str, Any], name: str, maximum: int) -> str | None:
        value = claims.get(name)
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value[:maximum] or None


class SelfServiceRoleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def options(self) -> list[RoleOptionResponse]:
        roles = await self._catalog()
        return [
            RoleOptionResponse(code=code, label=SELF_SERVICE_ROLE_DEFINITIONS[code][0], description=SELF_SERVICE_ROLE_DEFINITIONS[code][1])
            for code in sorted(roles)
        ]

    async def replace(
        self,
        principal: AuthenticatedPrincipal,
        requested_roles: list[str],
        *,
        request_id: uuid.UUID | None,
    ) -> MeResponse:
        desired = set(requested_roles)
        forbidden = desired - SELF_SERVICE_ROLE_CODES
        if forbidden:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="One or more roles cannot be self-assigned")

        catalog = await self._catalog()
        desired_ids = {catalog[code].id for code in desired}
        allowed_ids = {role.id for role in catalog.values()}
        existing_result = await self.session.execute(
            select(Role.code, Role.id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == principal.user_id, Role.id.in_(allowed_ids))
        )
        existing = {code: role_id for code, role_id in existing_result.all()}

        if set(existing) != desired:
            await self.session.execute(
                delete(UserRole).where(
                    UserRole.user_id == principal.user_id,
                    UserRole.role_id.in_(allowed_ids - desired_ids),
                )
            )
            for code in sorted(desired - set(existing)):
                await self.session.execute(
                    insert(UserRole)
                    .values(user_id=principal.user_id, role_id=catalog[code].id)
                    .on_conflict_do_nothing(index_elements=["user_id", "role_id"])
                )
            self.session.add(
                AuditLog(
                    actor_user_id=principal.user_id,
                    actor_type="user",
                    action="identity.self_service_roles_changed",
                    resource_type="user",
                    resource_id=principal.user_id,
                    request_id=request_id,
                    metadata_json={"previous_roles": sorted(existing), "selected_roles": sorted(desired)},
                )
            )
            await self.session.commit()

        all_roles_result = await self.session.execute(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == principal.user_id)
            .order_by(Role.code)
        )
        all_roles = tuple(all_roles_result.scalars().all())
        return MeResponse(
            id=principal.user_id,
            email=principal.email,
            roles=all_roles,
            needs_role_onboarding=not all_roles,
        )

    async def _catalog(self) -> dict[str, Role]:
        result = await self.session.execute(select(Role).where(Role.code.in_(SELF_SERVICE_ROLE_CODES)))
        roles = {role.code: role for role in result.scalars().all()}
        if set(roles) != SELF_SERVICE_ROLE_CODES:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Role catalog is unavailable")
        return roles
