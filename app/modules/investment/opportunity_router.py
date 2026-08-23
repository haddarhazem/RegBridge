import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.opportunity_schemas import OpportunityCreate, OpportunityPatch, OpportunityResponse, OpportunityVersionResponse
from app.modules.investment.opportunity_service import InvestmentOpportunityService
router = APIRouter(prefix="/investment-opportunities", tags=["investment-opportunities"])
Session = Annotated[AsyncSession, Depends(get_session)]; Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]
@router.post("", response_model=OpportunityResponse, status_code=status.HTTP_201_CREATED)
async def create(data: OpportunityCreate, principal: Principal, session: Session): return OpportunityResponse.model_validate(await InvestmentOpportunityService(session).create(principal, data))
@router.get("", response_model=list[OpportunityResponse])
async def active(principal: Principal, session: Session, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)): return [OpportunityResponse.model_validate(x) for x in await InvestmentOpportunityService(session).active(principal, limit, offset)]
@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get(opportunity_id: uuid.UUID, principal: Principal, session: Session): return OpportunityResponse.model_validate(await InvestmentOpportunityService(session).get(principal, opportunity_id))
@router.patch("/{opportunity_id}", response_model=OpportunityResponse)
async def update(opportunity_id: uuid.UUID, data: OpportunityPatch, principal: Principal, session: Session): return OpportunityResponse.model_validate(await InvestmentOpportunityService(session).update(principal, opportunity_id, data))
@router.post("/{opportunity_id}/publish", response_model=OpportunityResponse)
async def publish(opportunity_id: uuid.UUID, principal: Principal, session: Session): return OpportunityResponse.model_validate(await InvestmentOpportunityService(session).publish(principal, opportunity_id))
@router.post("/{opportunity_id}/close", response_model=OpportunityResponse)
async def close(opportunity_id: uuid.UUID, principal: Principal, session: Session): return OpportunityResponse.model_validate(await InvestmentOpportunityService(session).close(principal, opportunity_id))
@router.get("/{opportunity_id}/versions", response_model=list[OpportunityVersionResponse])
async def versions(opportunity_id: uuid.UUID, principal: Principal, session: Session): return [OpportunityVersionResponse.model_validate(x) for x in await InvestmentOpportunityService(session).versions(principal, opportunity_id)]
