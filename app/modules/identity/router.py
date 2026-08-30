from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.request_id import get_request_id
from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import (
    AuthenticatedPrincipal,
    MeResponse,
    PublicOIDCConfigResponse,
    RoleOptionResponse,
    RoleSelectionRequest,
)
from app.modules.identity.service import SelfServiceRoleService

router = APIRouter()


@router.get("/auth/config", response_model=PublicOIDCConfigResponse)
async def public_oidc_config(settings: Annotated[Settings, Depends(get_settings)]) -> PublicOIDCConfigResponse:
    if (
        not settings.oidc_issuer
        or not settings.oidc_client_id
        or not settings.oidc_redirect_uri
        or "openid" not in settings.oidc_scope.split()
    ):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Browser authentication is not configured")
    extra: dict[str, str] = {}
    if settings.oidc_authorization_audience:
        extra["audience"] = settings.oidc_authorization_audience
    if settings.oidc_resource:
        extra["resource"] = settings.oidc_resource
    return PublicOIDCConfigResponse(
        authority=settings.oidc_issuer,
        client_id=settings.oidc_client_id,
        redirect_uri=settings.oidc_redirect_uri,
        post_logout_redirect_uri=settings.oidc_post_logout_redirect_uri,
        scope=settings.oidc_scope,
        authorization_extra_params=extra,
    )


@router.get("/me", response_model=MeResponse)
async def me(principal: Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]) -> MeResponse:
    return MeResponse(id=principal.user_id, email=principal.email, roles=principal.roles, needs_role_onboarding=not principal.roles)


@router.get("/me/roles/options", response_model=list[RoleOptionResponse])
async def role_options(
    _: Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[RoleOptionResponse]:
    return await SelfServiceRoleService(session).options()


@router.put("/me/roles", response_model=MeResponse)
async def replace_roles(
    body: RoleSelectionRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeResponse:
    return await SelfServiceRoleService(session).replace(
        principal,
        body.roles,
        request_id=get_request_id(request),
    )
