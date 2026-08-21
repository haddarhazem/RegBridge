import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.identity.auth import (
    AuthenticationConfigurationError,
    InvalidAccessTokenError,
    get_token_validator,
)
from app.modules.identity.models import Role, User, UserIdentity, UserRole
from app.modules.identity.schemas import AuthenticatedPrincipal

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def authentication_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})


async def get_authenticated_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthenticatedPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise authentication_error()
    validator = get_token_validator()
    try:
        claims = await validator.validate(credentials.credentials)
    except InvalidAccessTokenError:
        logger.info("Rejected invalid bearer access token")
        raise authentication_error() from None
    except AuthenticationConfigurationError:
        logger.error("OIDC authentication is not configured or available")
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from None

    provider = validator.settings.oidc_issuer
    assert provider is not None
    result = await session.execute(
        select(UserIdentity, User).join(User, User.id == UserIdentity.user_id).where(
            UserIdentity.provider == provider,
            UserIdentity.provider_subject == claims["sub"],
        )
    )
    identity = result.one_or_none()
    if identity is None:
        raise HTTPException(status_code=403, detail="Identity is not provisioned")
    user_identity, user = identity
    if user.status != "active":
        raise HTTPException(status_code=403, detail="User account is unavailable")

    role_result = await session.execute(
        select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id).order_by(Role.code)
    )
    return AuthenticatedPrincipal(user_id=user.id, email=user.email, roles=tuple(role_result.scalars().all()), provider=user_identity.provider)


async def get_optional_authenticated_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthenticatedPrincipal | None:
    if credentials is None:
        return None
    return await get_authenticated_principal(credentials, session)
