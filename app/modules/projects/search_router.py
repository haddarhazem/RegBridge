from typing import Annotated
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.search_schemas import StartupSearchFilters, StartupSearchResponse
from app.modules.projects.search_service import StartupSearchService

router=APIRouter(prefix="/startups",tags=["startup-search"])
Session=Annotated[AsyncSession,Depends(get_session)]
Principal=Annotated[AuthenticatedPrincipal,Depends(get_authenticated_principal)]
ALLOWED=set(StartupSearchFilters.model_fields)

@router.get("/search",response_model=StartupSearchResponse)
async def search_startups(request: Request,principal: Principal,session: Session,filters: StartupSearchFilters=Depends()) -> StartupSearchResponse:
    unknown=set(request.query_params)-ALLOWED
    if unknown:
        from fastapi import HTTPException
        raise HTTPException(status_code=422,detail=f"Unknown startup search filter: {sorted(unknown)[0]}")
    return await StartupSearchService(session).search(principal,filters)
