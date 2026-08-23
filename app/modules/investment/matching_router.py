import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.matching_schemas import MatchingCreate, MatchingRunResponse
from app.modules.investment.matching_service import MatchingService

router = APIRouter(prefix="/investment-matches", tags=["investment-matching"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


@router.post("", response_model=MatchingRunResponse, status_code=status.HTTP_201_CREATED)
async def create_matching(data: MatchingCreate, principal: Principal, session: Session):
    return await MatchingService(session).create(principal, data.startup_project_id, data.investor_thesis_version_id)


@router.get("/{run_id}", response_model=MatchingRunResponse)
async def get_matching(run_id: uuid.UUID, principal: Principal, session: Session):
    return await MatchingService(session).get(principal, run_id)
