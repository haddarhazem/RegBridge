import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.network.schemas import ContactAccept, ContactDisclosure, ContactPointCreate, ContactPointResponse, ContactRequestCreate, ContactRequestResponse, ConsentResponse
from app.modules.network.service import ContactRequestService
router = APIRouter(prefix="/contact-requests", tags=["contact"])
Session = Annotated[AsyncSession, Depends(get_session)]; Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]
@router.post("/contact-points", response_model=ContactPointResponse, status_code=status.HTTP_201_CREATED)
async def create_point(data: ContactPointCreate, principal: Principal, session: Session): return await ContactRequestService(session).create_point(principal, data)
@router.get("/contact-points", response_model=list[ContactPointResponse])
async def points(principal: Principal, session: Session): return await ContactRequestService(session).points(principal)
@router.post("", response_model=ContactRequestResponse, status_code=status.HTTP_201_CREATED)
async def create(data: ContactRequestCreate, principal: Principal, session: Session): return await ContactRequestService(session).create(principal, data)
@router.get("", response_model=list[ContactRequestResponse])
async def list_requests(principal: Principal, session: Session, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)): return await ContactRequestService(session).list(principal, limit, offset)
@router.post("/{request_id}/accept", response_model=ContactRequestResponse)
async def accept(request_id: uuid.UUID, data: ContactAccept, principal: Principal, session: Session): return await ContactRequestService(session).accept(principal, request_id, data)
@router.post("/{request_id}/refuse", response_model=ContactRequestResponse)
async def refuse(request_id: uuid.UUID, principal: Principal, session: Session): return await ContactRequestService(session).refuse(principal, request_id)
@router.get("/{request_id}/contacts", response_model=ContactDisclosure)
async def disclose(request_id: uuid.UUID, principal: Principal, session: Session): return await ContactRequestService(session).disclose(principal, request_id)
@router.post("/consents/{consent_id}/revoke", response_model=ConsentResponse)
async def revoke(consent_id: uuid.UUID, principal: Principal, session: Session): return await ContactRequestService(session).revoke(principal, consent_id)
