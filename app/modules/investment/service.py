from __future__ import annotations
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.audit import AuditLog
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.models import InvestorProfile, InvestorThesisVersion
from app.modules.investment.schemas import ThesisCreate, ThesisPatch

LIST_FIELDS = ("sectors", "stages", "geographies", "technologies")
VALUE_FIELDS = LIST_FIELDS + ("ticket_min", "ticket_max", "ticket_currency")

def normalize_list(value: list[str] | None) -> list[str] | None:
    if value is None: return None
    result=[]
    for item in value:
        cleaned=item.strip()
        if cleaned and cleaned not in result: result.append(cleaned)
    return result

def normalized_values(data: ThesisCreate | ThesisPatch) -> dict:
    values={}
    provided = data.model_fields_set
    for field in VALUE_FIELDS:
        if field not in provided: continue
        value=getattr(data,field)
        values[field]=normalize_list(value) if field in LIST_FIELDS else value
    return values

def validate_range(values: dict) -> None:
    minimum, maximum = values.get("ticket_min"), values.get("ticket_max")
    if minimum is not None and maximum is not None and minimum > maximum: raise HTTPException(status_code=422, detail="ticket_min must be less than or equal to ticket_max")

class InvestorProfileService:
    def __init__(self, session: AsyncSession) -> None: self.session=session

    async def _owned_profile(self, actor: AuthenticatedPrincipal) -> InvestorProfile:
        profile=await self.session.scalar(select(InvestorProfile).where(InvestorProfile.user_id == actor.user_id))
        if profile is None: raise HTTPException(status_code=404, detail="Investor profile not found")
        return profile

    async def _response(self, profile: InvestorProfile) -> InvestorProfile:
        if profile.current_version_id:
            profile.current_version=await self.session.get(InvestorThesisVersion, profile.current_version_id)
        else: profile.current_version=None
        return profile

    async def create(self, actor: AuthenticatedPrincipal, data: ThesisCreate) -> InvestorProfile:
        existing=await self.session.scalar(select(InvestorProfile).where(InvestorProfile.user_id == actor.user_id))
        if existing is not None: raise HTTPException(status_code=409, detail="Investor profile already exists")
        values=normalized_values(data); validate_range(values)
        profile=InvestorProfile(user_id=actor.user_id); self.session.add(profile); await self.session.flush()
        version=InvestorThesisVersion(investor_profile_id=profile.id,version_number=1,created_by_user_id=actor.user_id,**{field:values.get(field) for field in VALUE_FIELDS})
        self.session.add(version); await self.session.flush(); profile.current_version_id=version.id
        self.session.add(AuditLog(actor_user_id=actor.user_id,actor_type="user",action="investor_thesis.created",resource_type="investor_thesis_version",resource_id=version.id,metadata_json={"version":1}))
        await self.session.commit(); return await self._response(profile)

    async def get(self, actor: AuthenticatedPrincipal) -> InvestorProfile: return await self._response(await self._owned_profile(actor))

    async def update(self, actor: AuthenticatedPrincipal, data: ThesisPatch) -> InvestorProfile:
        profile=await self.session.scalar(select(InvestorProfile).where(InvestorProfile.user_id == actor.user_id).with_for_update())
        if profile is None: raise HTTPException(status_code=404, detail="Investor profile not found")
        if profile.current_version_id != data.expected_version_id: raise HTTPException(status_code=409, detail="Investor thesis version is stale")
        current=await self.session.get(InvestorThesisVersion, profile.current_version_id)
        values={field:getattr(current,field) for field in VALUE_FIELDS}; values.update(normalized_values(data)); validate_range(values)
        if all(values[field] == getattr(current,field) for field in VALUE_FIELDS): return await self._response(profile)
        version=InvestorThesisVersion(investor_profile_id=profile.id,version_number=current.version_number+1,created_by_user_id=actor.user_id,**values)
        self.session.add(version); await self.session.flush(); profile.current_version_id=version.id
        self.session.add(AuditLog(actor_user_id=actor.user_id,actor_type="user",action="investor_thesis.updated",resource_type="investor_thesis_version",resource_id=version.id,metadata_json={"from_version":current.version_number,"to_version":version.version_number}))
        await self.session.commit(); return await self._response(profile)

    async def versions(self, actor: AuthenticatedPrincipal) -> list[InvestorThesisVersion]:
        profile=await self._owned_profile(actor)
        return list((await self.session.scalars(select(InvestorThesisVersion).where(InvestorThesisVersion.investor_profile_id == profile.id).order_by(InvestorThesisVersion.version_number))).all())

    async def version(self, actor: AuthenticatedPrincipal, version_id: uuid.UUID) -> InvestorThesisVersion:
        profile=await self._owned_profile(actor)
        item=await self.session.scalar(select(InvestorThesisVersion).where(InvestorThesisVersion.id == version_id, InvestorThesisVersion.investor_profile_id == profile.id))
        if item is None: raise HTTPException(status_code=404, detail="Investor thesis version not found")
        return item
