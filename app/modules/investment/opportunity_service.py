from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.audit import AuditLog
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.models import InvestmentOpportunity, InvestmentOpportunityVersion, InvestorProfile
from app.modules.investment.opportunity_schemas import OpportunityCreate, OpportunityPatch

FIELDS = ("title", "description", "opportunity_type", "criteria", "visibility", "application_deadline")

class InvestmentOpportunityService:
    def __init__(self, session: AsyncSession) -> None: self.session = session
    async def _profile(self, actor: AuthenticatedPrincipal) -> InvestorProfile:
        profile = await self.session.scalar(select(InvestorProfile).where(InvestorProfile.user_id == actor.user_id))
        if profile is None: raise HTTPException(status_code=404, detail="Investor profile not found")
        return profile
    async def _owned(self, actor, item_id, lock=False):
        profile = await self._profile(actor); query = select(InvestmentOpportunity).where(InvestmentOpportunity.id == item_id, InvestmentOpportunity.investor_profile_id == profile.id)
        if lock: query = query.with_for_update().execution_options(populate_existing=True)
        item = await self.session.scalar(query)
        if item is None: raise HTTPException(status_code=404, detail="Investment opportunity not found")
        return item
    async def _current(self, item):
        current = await self.session.get(InvestmentOpportunityVersion, item.current_version_id)
        if current is None: raise HTTPException(status_code=409, detail="Opportunity current version is missing")
        return current
    async def _response(self, item):
        current = await self._current(item)
        return self._apply_response(item, current)
    def _apply_response(self, item, current):
        for field in FIELDS + ("status", "published_at"): setattr(item, field, getattr(current, field))
        item.version_number = current.version_number
        return item
    async def _new_version(self, item, actor, values, number):
        version = InvestmentOpportunityVersion(opportunity_id=item.id, version_number=number, created_by_user_id=actor.user_id, **values)
        self.session.add(version); await self.session.flush(); item.current_version_id = version.id
        return version
    async def create(self, actor, data: OpportunityCreate):
        profile = await self._profile(actor); published = datetime.now(timezone.utc) if data.status == "PUBLISHED" else None
        values = {field: getattr(data, field) for field in FIELDS}; values.update(status=data.status, published_at=published)
        item = InvestmentOpportunity(investor_profile_id=profile.id, **values); self.session.add(item); await self.session.flush()
        version = await self._new_version(item, actor, values, 1)
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="investment_opportunity.created", resource_type="investment_opportunity_version", resource_id=version.id, metadata_json={"version":1}))
        await self.session.commit(); return await self._response(item)
    async def get(self, actor, item_id): return await self._response(await self._owned(actor, item_id))
    async def update(self, actor, item_id, data: OpportunityPatch):
        item = await self._owned(actor, item_id, True); current = await self._current(item)
        if current.status == "CLOSED": raise HTTPException(status_code=409, detail="Closed opportunity cannot be updated")
        if current.id != data.expected_version_id: raise HTTPException(status_code=409, detail="Investment opportunity version is stale")
        values = {field: getattr(current, field) for field in FIELDS}
        for field in FIELDS:
            if field in data.model_fields_set: values[field] = getattr(data, field)
        for field in ("title", "description", "opportunity_type", "visibility"):
            if values[field] is None: raise HTTPException(status_code=422, detail=f"{field} cannot be cleared")
        if values["criteria"] is None: values["criteria"] = {}
        if all(values[field] == getattr(current, field) for field in FIELDS): return await self._response(item)
        version = await self._new_version(item, actor, {**values, "status":current.status, "published_at":current.published_at}, current.version_number + 1)
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="investment_opportunity.updated", resource_type="investment_opportunity_version", resource_id=version.id, metadata_json={"from_version":current.version_number,"to_version":version.version_number}))
        await self.session.commit(); return await self._response(item)
    async def _transition(self, actor, item_id, target):
        item = await self._owned(actor, item_id, True); current = await self._current(item)
        if target == "PUBLISHED" and current.status == "CLOSED": raise HTTPException(status_code=409, detail="Closed opportunity cannot be reopened")
        if current.status == target: return await self._response(item)
        values = {field:getattr(current, field) for field in FIELDS}; values.update(status=target, published_at=current.published_at or datetime.now(timezone.utc) if target == "PUBLISHED" else current.published_at)
        version = await self._new_version(item, actor, values, current.version_number + 1)
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action=f"investment_opportunity.{target.lower()}", resource_type="investment_opportunity_version", resource_id=version.id, metadata_json={"version":version.version_number}))
        await self.session.commit(); return await self._response(item)
    async def publish(self, actor, item_id): return await self._transition(actor, item_id, "PUBLISHED")
    async def close(self, actor, item_id): return await self._transition(actor, item_id, "CLOSED")
    async def versions(self, actor, item_id):
        item = await self._owned(actor, item_id)
        return list((await self.session.scalars(select(InvestmentOpportunityVersion).where(InvestmentOpportunityVersion.opportunity_id == item.id).order_by(InvestmentOpportunityVersion.version_number))).all())
    async def active(self, actor, limit=50, offset=0):
        await self._profile(actor); now = datetime.now(timezone.utc)
        rows = list((await self.session.execute(select(InvestmentOpportunity, InvestmentOpportunityVersion).join(InvestmentOpportunityVersion, InvestmentOpportunityVersion.id == InvestmentOpportunity.current_version_id).where(InvestmentOpportunityVersion.status == "PUBLISHED", InvestmentOpportunityVersion.visibility.in_(("AUTHENTICATED", "PUBLIC")), or_(InvestmentOpportunityVersion.application_deadline.is_(None), InvestmentOpportunityVersion.application_deadline >= now)).order_by(InvestmentOpportunityVersion.published_at.desc().nullslast(), InvestmentOpportunity.id).offset(offset).limit(limit))).all())
        items = [self._apply_response(item, current) for item, current in rows]
        return items
