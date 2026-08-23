import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.schemas import InvestorProfileResponse, ThesisCreate, ThesisPatch, ThesisVersionResponse
from app.modules.investment.service import InvestorProfileService

router=APIRouter(prefix="/investor",tags=["investment"])
Session=Annotated[AsyncSession,Depends(get_session)]
Principal=Annotated[AuthenticatedPrincipal,Depends(get_authenticated_principal)]

@router.post("/profile",response_model=InvestorProfileResponse,status_code=status.HTTP_201_CREATED)
async def create_profile(data: ThesisCreate,principal: Principal,session: Session)->InvestorProfileResponse:
    return InvestorProfileResponse.model_validate(await InvestorProfileService(session).create(principal,data))

@router.get("/profile",response_model=InvestorProfileResponse)
async def get_profile(principal: Principal,session: Session)->InvestorProfileResponse:
    return InvestorProfileResponse.model_validate(await InvestorProfileService(session).get(principal))

@router.patch("/profile",response_model=InvestorProfileResponse)
async def update_profile(data: ThesisPatch,principal: Principal,session: Session)->InvestorProfileResponse:
    return InvestorProfileResponse.model_validate(await InvestorProfileService(session).update(principal,data))

@router.get("/profile/versions",response_model=list[ThesisVersionResponse])
async def list_versions(principal: Principal,session: Session)->list[ThesisVersionResponse]:
    return [ThesisVersionResponse.model_validate(item) for item in await InvestorProfileService(session).versions(principal)]

@router.get("/profile/versions/{version_id}",response_model=ThesisVersionResponse)
async def get_version(version_id: uuid.UUID,principal: Principal,session: Session)->ThesisVersionResponse:
    return ThesisVersionResponse.model_validate(await InvestorProfileService(session).version(principal,version_id))
