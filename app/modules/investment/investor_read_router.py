from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.brief_schemas import BriefListItem
from app.modules.investment.brief_service import OpportunityBriefService
from app.modules.investment.matching_schemas import MatchingListItem
from app.modules.investment.matching_service import MatchingService


router = APIRouter(prefix="/investor", tags=["investor-read"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]
BoundedLimit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/matches", response_model=list[MatchingListItem])
async def list_owned_matches(principal: Principal, session: Session, limit: BoundedLimit = 50, offset: Offset = 0) -> list[MatchingListItem]:
    return await MatchingService(session).list_owned(principal, limit, offset)


@router.get("/briefs", response_model=list[BriefListItem])
async def list_owned_briefs(principal: Principal, session: Session, limit: BoundedLimit = 50, offset: Offset = 0) -> list[BriefListItem]:
    return await OpportunityBriefService(session).list_owned(principal, limit, offset)
