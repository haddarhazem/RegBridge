import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.sharing.schemas import RevokeShareRequest, ShareGrantCreate, ShareGrantResponse, SharedResourceResponse
from app.modules.sharing.service import SharingService

router = APIRouter(tags=["sharing"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]

@router.post("/projects/{project_id}/shares", response_model=ShareGrantResponse, status_code=status.HTTP_201_CREATED)
async def create_share(project_id: uuid.UUID, data: ShareGrantCreate, principal: Principal, session: Session) -> ShareGrantResponse:
    return ShareGrantResponse.model_validate(await SharingService(session).create(principal, project_id, data))

@router.get("/projects/{project_id}/shares", response_model=list[ShareGrantResponse])
async def list_shares(project_id: uuid.UUID, principal: Principal, session: Session) -> list[ShareGrantResponse]:
    return [ShareGrantResponse.model_validate(item) for item in await SharingService(session).list(principal, project_id)]

@router.post("/projects/{project_id}/shares/{grant_id}/revoke", response_model=ShareGrantResponse)
async def revoke_share(project_id: uuid.UUID, grant_id: uuid.UUID, data: RevokeShareRequest, principal: Principal, session: Session) -> ShareGrantResponse:
    return ShareGrantResponse.model_validate(await SharingService(session).revoke(principal, project_id, grant_id, data))

@router.get("/shared/{grant_id}/resource", response_model=SharedResourceResponse)
async def shared_resource(grant_id: uuid.UUID, principal: Principal, session: Session) -> SharedResourceResponse:
    grant, payload = await SharingService(session).access(principal, grant_id)
    return SharedResourceResponse(grant_id=grant.id, project_id=grant.project_id, resource_type=grant.resource_type, resource_id=grant.resource_id, resource_version_id=grant.resource_version_id, scope=grant.scope, payload=payload)
