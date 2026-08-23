from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.audit import AuditLog
from app.modules.events.models import EcosystemEvent, EventRegistration
from app.modules.events.schemas import EventCreate, EventPatch, ParticipationResponse
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.models import InvestorProfile

class EventService:
    def __init__(self, session: AsyncSession) -> None: self.session = session
    async def _event(self, event_id: uuid.UUID, lock: bool = False) -> EcosystemEvent:
        query = select(EcosystemEvent).where(EcosystemEvent.id == event_id)
        if lock: query = query.with_for_update().execution_options(populate_existing=True)
        event = await self.session.scalar(query)
        if event is None: raise HTTPException(status_code=404, detail="Event not found")
        return event
    async def _organizer(self, actor: AuthenticatedPrincipal, event_id: uuid.UUID, lock: bool = False) -> EcosystemEvent:
        event = await self._event(event_id, lock)
        if event.organizer_user_id != actor.user_id: raise HTTPException(status_code=403, detail="Organizer access required")
        return event
    async def create(self, actor: AuthenticatedPrincipal, data: EventCreate) -> EcosystemEvent:
        profile = await self.session.scalar(select(InvestorProfile).where(InvestorProfile.user_id == actor.user_id))
        event = EcosystemEvent(organizer_user_id=actor.user_id, investor_profile_id=profile.id if profile else None, **data.model_dump())
        self.session.add(event); await self.session.flush()
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="EVENT_CREATED", resource_type="ecosystem_event", resource_id=event.id, metadata_json={"event_type":event.event_type}))
        await self.session.commit(); return event
    async def get(self, actor: AuthenticatedPrincipal, event_id: uuid.UUID) -> EcosystemEvent: return await self._event(event_id)
    async def update(self, actor: AuthenticatedPrincipal, event_id: uuid.UUID, data: EventPatch) -> EcosystemEvent:
        event = await self._organizer(actor, event_id, True)
        if event.status == "cancelled": raise HTTPException(status_code=409, detail="Cancelled event cannot be updated")
        if data.expected_updated_at and event.updated_at != data.expected_updated_at: raise HTTPException(status_code=409, detail="Event update is stale")
        values = data.model_dump(exclude_unset=True, exclude={"expected_updated_at"})
        merged = {field: values.get(field, getattr(event, field)) for field in ("starts_at", "ends_at")}
        if merged["starts_at"] is None or merged["ends_at"] is None: raise HTTPException(status_code=422, detail="event dates cannot be cleared")
        if merged["starts_at"] >= merged["ends_at"]: raise HTTPException(status_code=422, detail="starts_at must be before ends_at")
        for field, value in values.items(): setattr(event, field, value)
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="EVENT_UPDATED", resource_type="ecosystem_event", resource_id=event.id, metadata_json={"fields":sorted(values)}))
        await self.session.commit(); return event
    async def cancel(self, actor: AuthenticatedPrincipal, event_id: uuid.UUID) -> EcosystemEvent:
        event = await self._organizer(actor, event_id, True)
        if event.status != "cancelled":
            event.status = "cancelled"
            self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="EVENT_CANCELLED", resource_type="ecosystem_event", resource_id=event.id, metadata_json={}))
            await self.session.commit()
        return event
    async def active(self, actor: AuthenticatedPrincipal, limit: int = 50, offset: int = 0) -> list[EcosystemEvent]:
        now = datetime.now(timezone.utc)
        return list((await self.session.scalars(select(EcosystemEvent).where(EcosystemEvent.status == "active", EcosystemEvent.ends_at >= now).order_by(EcosystemEvent.starts_at, EcosystemEvent.id).offset(offset).limit(limit))).all())
    async def _participation(self, actor, event_id, target):
        event = await self._event(event_id, True)
        if event.status == "cancelled" and target != "withdrawn": raise HTTPException(status_code=409, detail="Cancelled event does not accept new participation")
        row = await self.session.scalar(select(EventRegistration).where(EventRegistration.event_id == event.id, EventRegistration.user_id == actor.user_id).with_for_update())
        if target == "withdrawn":
            if row is None:
                row = EventRegistration(event_id=event.id, user_id=actor.user_id, status="withdrawn"); self.session.add(row)
                await self.session.flush()
                self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="WITHDRAWN", resource_type="event_registration", resource_id=row.id, metadata_json={"event_id":str(event.id)}))
            elif row.status != "withdrawn":
                row.status = "withdrawn"; self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="WITHDRAWN", resource_type="event_registration", resource_id=row.id, metadata_json={"event_id":str(event.id)}))
        else:
            if row is None:
                row = EventRegistration(event_id=event.id, user_id=actor.user_id, status=target); self.session.add(row)
                await self.session.flush()
                self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="INTEREST_EXPRESSED" if target == "interested" else "REGISTERED", resource_type="event_registration", resource_id=row.id, metadata_json={"event_id":str(event.id)}))
            elif row.status != target:
                row.status = target; self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="REGISTERED" if target == "registered" else "INTEREST_EXPRESSED", resource_type="event_registration", resource_id=row.id, metadata_json={"event_id":str(event.id)}))
        await self.session.commit(); return row
    async def interest(self, actor, event_id): return await self._participation(actor, event_id, "interested")
    async def register(self, actor, event_id): return await self._participation(actor, event_id, "registered")
    async def withdraw(self, actor, event_id): return await self._participation(actor, event_id, "withdrawn")
    async def participation(self, actor, event_id):
        await self._event(event_id); row = await self.session.scalar(select(EventRegistration).where(EventRegistration.event_id == event_id, EventRegistration.user_id == actor.user_id))
        return ParticipationResponse(event_id=event_id, user_id=actor.user_id, status=row.status if row else None, active=bool(row and row.status != "withdrawn"))
