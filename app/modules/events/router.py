import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.modules.events.schemas import EventCreate, EventPatch, EventRegistrationResponse, EventResponse, ParticipationResponse
from app.modules.events.service import EventService
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/events", tags=["events"])
Session = Annotated[AsyncSession, Depends(get_session)]; Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]
@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create(data: EventCreate, principal: Principal, session: Session): return await EventService(session).create(principal, data)
@router.get("", response_model=list[EventResponse])
async def active(principal: Principal, session: Session, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)): return await EventService(session).active(principal, limit, offset)
@router.get("/{event_id}", response_model=EventResponse)
async def get(event_id: uuid.UUID, principal: Principal, session: Session): return await EventService(session).get(principal, event_id)
@router.patch("/{event_id}", response_model=EventResponse)
async def update(event_id: uuid.UUID, data: EventPatch, principal: Principal, session: Session): return await EventService(session).update(principal, event_id, data)
@router.post("/{event_id}/cancel", response_model=EventResponse)
async def cancel(event_id: uuid.UUID, principal: Principal, session: Session): return await EventService(session).cancel(principal, event_id)
@router.post("/{event_id}/interest", response_model=EventRegistrationResponse)
async def interest(event_id: uuid.UUID, principal: Principal, session: Session): return await EventService(session).interest(principal, event_id)
@router.post("/{event_id}/register", response_model=EventRegistrationResponse)
async def register(event_id: uuid.UUID, principal: Principal, session: Session): return await EventService(session).register(principal, event_id)
@router.post("/{event_id}/withdraw", response_model=EventRegistrationResponse)
async def withdraw(event_id: uuid.UUID, principal: Principal, session: Session): return await EventService(session).withdraw(principal, event_id)
@router.get("/{event_id}/participation", response_model=ParticipationResponse)
async def participation(event_id: uuid.UUID, principal: Principal, session: Session): return await EventService(session).participation(principal, event_id)
