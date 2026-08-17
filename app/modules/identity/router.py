from typing import Annotated

from fastapi import APIRouter, Depends

from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal, MeResponse

router = APIRouter()


@router.get("/me", response_model=MeResponse)
async def me(principal: Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]) -> MeResponse:
    return MeResponse(id=principal.user_id, email=principal.email, roles=principal.roles)
