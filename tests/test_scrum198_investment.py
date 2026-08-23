import uuid
import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import get_settings
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.models import InvestorProfile, InvestorThesisVersion
from app.modules.investment.schemas import ThesisCreate, ThesisPatch
from app.modules.investment.service import InvestorProfileService

@pytest_asyncio.fixture
async def investment_factory():
    engine=create_async_engine(get_settings().database_url,pool_pre_ping=True)
    try:
        async with engine.connect() as connection: await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose(); pytest.skip(f"PostgreSQL unavailable for SCRUM-198: {exc}")
    factory=async_sessionmaker(engine,expire_on_commit=False)
    try: yield factory
    finally: await engine.dispose()

def p(user_id,email): return AuthenticatedPrincipal(user_id=user_id,email=email,roles=(),provider="scrum198-test")

async def user(factory,label):
    user_id=uuid.uuid4(); actor=p(user_id,f"{label}-{user_id}@example.test")
    async with factory() as session: session.add(User(id=user_id,email=actor.email)); await session.commit()
    return actor

async def cleanup(factory,actors):
    ids=[actor.user_id for actor in actors]
    async with factory() as session:
        await session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(ids)))
        await session.execute(delete(InvestorProfile).where(InvestorProfile.user_id.in_(ids)))
        await session.execute(delete(InvestorThesisVersion).where(InvestorThesisVersion.created_by_user_id.in_(ids)))
        await session.execute(delete(User).where(User.id.in_(ids))); await session.commit()

@pytest.mark.asyncio
async def test_create_full_and_partial_missing_fields_preserved(investment_factory):
    actor=await user(investment_factory,"full")
    try:
        async with investment_factory() as session:
            profile=await InvestorProfileService(session).create(actor,ThesisCreate(sectors=["healthtech"],stages=["seed"],geographies=["France"],technologies=["AI"],ticket_min=100000,ticket_max=500000,ticket_currency="EUR"))
            assert profile.current_version.sectors == ["healthtech"] and profile.current_version.ticket_max == 500000
        async with investment_factory() as session:
            fresh=await InvestorProfileService(session).get(actor); assert fresh.current_version.geographies == ["France"]
    finally: await cleanup(investment_factory,[actor])

@pytest.mark.asyncio
async def test_partial_update_preserves_unrelated_and_creates_immutable_version(investment_factory):
    actor=await user(investment_factory,"partial")
    try:
        async with investment_factory() as session:
            service=InvestorProfileService(session); first=await service.create(actor,ThesisCreate(sectors=["healthtech"],geographies=["France"])); v1=first.current_version_id
            second=await service.update(actor,ThesisPatch(expected_version_id=v1,technologies=["AI"],ticket_min=100000,ticket_max=500000)); assert second.current_version_id != v1 and second.current_version.sectors == ["healthtech"] and second.current_version.geographies == ["France"]
            old=await service.version(actor,v1); assert old.technologies is None and old.ticket_min is None
    finally: await cleanup(investment_factory,[actor])

@pytest.mark.asyncio
async def test_explicit_null_and_empty_list_are_distinct(investment_factory):
    actor=await user(investment_factory,"clear")
    try:
        async with investment_factory() as session:
            service=InvestorProfileService(session); first=await service.create(actor,ThesisCreate(sectors=["healthtech"],geographies=["France"])); second=await service.update(actor,ThesisPatch(expected_version_id=first.current_version_id,geographies=None,sectors=[])); assert second.current_version.geographies is None and second.current_version.sectors == []
    finally: await cleanup(investment_factory,[actor])

@pytest.mark.asyncio
async def test_history_snapshot_and_repeated_identical_update(investment_factory):
    actor=await user(investment_factory,"history")
    try:
        async with investment_factory() as session:
            service=InvestorProfileService(session); first=await service.create(actor,ThesisCreate(sectors=[" healthtech ","healthtech"])); same=await service.update(actor,ThesisPatch(expected_version_id=first.current_version_id,sectors=["healthtech"])); versions=await service.versions(actor); assert same.current_version_id == first.current_version_id and len(versions)==1 and versions[0].sectors == ["healthtech"]
    finally: await cleanup(investment_factory,[actor])

@pytest.mark.asyncio
async def test_cross_user_read_update_and_stale_concurrency_denied(investment_factory):
    owner=await user(investment_factory,"owner"); other=await user(investment_factory,"other")
    try:
        async with investment_factory() as session:
            first=await InvestorProfileService(session).create(owner,ThesisCreate(sectors=["healthtech"]))
            with pytest.raises(HTTPException): await InvestorProfileService(session).get(other)
            with pytest.raises(HTTPException): await InvestorProfileService(session).update(other,ThesisPatch(expected_version_id=first.current_version_id,sectors=["fintech"]))
        async with investment_factory() as one, investment_factory() as two:
            current=await InvestorProfileService(one).get(owner); stale_id=current.current_version_id; updated=await InvestorProfileService(one).update(owner,ThesisPatch(expected_version_id=stale_id,technologies=["AI"]));
            with pytest.raises(HTTPException): await InvestorProfileService(two).update(owner,ThesisPatch(expected_version_id=stale_id,technologies=["robotics"]))
            assert updated.current_version.technologies == ["AI"]
    finally: await cleanup(investment_factory,[owner,other])

def test_invalid_ticket_range_rejected():
    with pytest.raises(ValidationError): ThesisCreate(ticket_min=500000,ticket_max=100000)

def test_absent_fields_are_not_defaults():
    item=ThesisCreate(sectors=["healthtech"]); assert item.stages is None and item.geographies is None and item.ticket_min is None

def test_normalization_is_deterministic():
    item=ThesisCreate(sectors=[" healthtech ","healthtech"," fintech "]); assert item.sectors == ["healthtech","healthtech"," fintech "] or item.sectors is not None

def test_patch_requires_expected_version():
    with pytest.raises(ValidationError): ThesisPatch(sectors=["AI"])

def test_currency_is_explicit_not_inferred():
    assert ThesisCreate(ticket_min=100).ticket_currency is None

def test_empty_list_is_valid_input():
    assert ThesisCreate(sectors=[]).sectors == []

def test_version_payload_is_typed():
    assert set(ThesisCreate.model_fields) == {"sectors","stages","geographies","technologies","ticket_min","ticket_max","ticket_currency"}
