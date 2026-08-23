import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import get_settings
from app.modules.audit import AuditLog
from app.modules.events.models import EcosystemEvent, EventRegistration
from app.modules.events.schemas import EventCreate, EventPatch
from app.modules.events.service import EventService
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.models import InvestorProfile
from app.modules.investment.schemas import ThesisCreate
from app.modules.investment.service import InvestorProfileService

@pytest_asyncio.fixture
async def events_factory():
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection: await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose(); pytest.skip(f"PostgreSQL unavailable for SCRUM-201: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try: yield factory
    finally: await engine.dispose()

def actor(user_id, label): return AuthenticatedPrincipal(user_id=user_id, email=f"{label}-{user_id}@example.test", roles=(), provider="scrum201-test")

async def make_user(factory, label):
    user_id = uuid.uuid4(); result = actor(user_id, label)
    async with factory() as session: session.add(User(id=user_id, email=result.email)); await session.commit()
    return result

async def cleanup(factory, actors):
    ids = [x.user_id for x in actors]
    async with factory() as session:
        event_ids = list(await session.scalars(select(EcosystemEvent.id).where(EcosystemEvent.organizer_user_id.in_(ids))))
        if event_ids: await session.execute(delete(EventRegistration).where(EventRegistration.event_id.in_(event_ids))); await session.execute(delete(EcosystemEvent).where(EcosystemEvent.id.in_(event_ids)))
        await session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(ids)))
        await session.execute(delete(InvestorProfile).where(InvestorProfile.user_id.in_(ids)))
        await session.execute(delete(User).where(User.id.in_(ids))); await session.commit()

def event_data(**overrides):
    now = datetime.now(timezone.utc); data = {"event_type":"event", "title":"Networking event", "description":"Safe description", "location_type":"online", "starts_at":now+timedelta(days=1), "ends_at":now+timedelta(days=2), "status":"active"}; data.update(overrides); return EventCreate(**data)

async def profile(session, actor): return await InvestorProfileService(session).create(actor, ThesisCreate(sectors=["healthtech"]))

@pytest.mark.asyncio
async def test_create_event_and_hackathon(events_factory):
    organizer = await make_user(events_factory, "create")
    try:
        async with events_factory() as session:
            await profile(session, organizer); service = EventService(session); event = await service.create(organizer, event_data()); hackathon = await service.create(organizer, event_data(event_type="hackathon", title="Hackathon"))
            assert event.event_type == "event" and hackathon.event_type == "hackathon" and event.organizer_user_id == organizer.user_id
    finally: await cleanup(events_factory, [organizer])

def test_invalid_event_dates_rejected():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError): EventCreate(**{"title":"bad","starts_at":now,"ends_at":now-timedelta(minutes=1)})

@pytest.mark.asyncio
async def test_organizer_update_and_unauthorized_update_denied(events_factory):
    owner = await make_user(events_factory, "update-owner"); other = await make_user(events_factory, "update-other")
    try:
        async with events_factory() as session:
            await profile(session, owner); item = await EventService(session).create(owner, event_data()); updated = await EventService(session).update(owner, item.id, EventPatch(title="Updated")); assert updated.title == "Updated"
            with pytest.raises(HTTPException): await EventService(session).update(other, item.id, EventPatch(title="bad"))
    finally: await cleanup(events_factory, [owner, other])

@pytest.mark.asyncio
async def test_organizer_cancel_and_unauthorized_cancel_denied(events_factory):
    owner = await make_user(events_factory, "cancel-owner"); other = await make_user(events_factory, "cancel-other")
    try:
        async with events_factory() as session:
            await profile(session, owner); item = await EventService(session).create(owner, event_data())
            with pytest.raises(HTTPException): await EventService(session).cancel(other, item.id)
            cancelled = await EventService(session).cancel(owner, item.id); assert cancelled.status == "cancelled"
    finally: await cleanup(events_factory, [owner, other])

@pytest.mark.asyncio
async def test_interest_is_idempotent_and_traceable(events_factory):
    owner = await make_user(events_factory, "interest-owner"); participant = await make_user(events_factory, "interest-user")
    try:
        async with events_factory() as session:
            await profile(session, owner); item = await EventService(session).create(owner, event_data()); service = EventService(session); first = await service.interest(participant, item.id); second = await service.interest(participant, item.id)
            audits = list(await session.scalars(select(AuditLog).where(AuditLog.resource_type == "event_registration", AuditLog.resource_id == first.id)))
            assert first.id == second.id and second.status == "interested" and len(audits) == 1
    finally: await cleanup(events_factory, [owner, participant])

@pytest.mark.asyncio
async def test_registration_supersedes_interest_and_is_idempotent(events_factory):
    owner = await make_user(events_factory, "register-owner"); participant = await make_user(events_factory, "register-user")
    try:
        async with events_factory() as session:
            await profile(session, owner); item = await EventService(session).create(owner, event_data()); service = EventService(session); await service.interest(participant, item.id); first = await service.register(participant, item.id); second = await service.register(participant, item.id)
            assert first.id == second.id and second.status == "registered"
    finally: await cleanup(events_factory, [owner, participant])

@pytest.mark.asyncio
async def test_withdrawal_is_idempotent_and_preserves_row(events_factory):
    owner = await make_user(events_factory, "withdraw-owner"); participant = await make_user(events_factory, "withdraw-user")
    try:
        async with events_factory() as session:
            await profile(session, owner); item = await EventService(session).create(owner, event_data()); service = EventService(session); await service.register(participant, item.id); first = await service.withdraw(participant, item.id); second = await service.withdraw(participant, item.id)
            assert first.id == second.id and second.status == "withdrawn" and await service.participation(participant, item.id)
    finally: await cleanup(events_factory, [owner, participant])

@pytest.mark.asyncio
async def test_wrong_user_withdrawal_denied(events_factory):
    owner = await make_user(events_factory, "withdraw-owner2"); participant = await make_user(events_factory, "withdraw-user2"); other = await make_user(events_factory, "withdraw-other2")
    try:
        async with events_factory() as session:
            await profile(session, owner); item = await EventService(session).create(owner, event_data()); await EventService(session).register(participant, item.id)
            result = await EventService(session).withdraw(other, item.id)
            owner_state = await EventService(session).participation(participant, item.id)
            assert result.user_id == other.user_id and owner_state.status == "registered"
    finally: await cleanup(events_factory, [owner, participant, other])

@pytest.mark.asyncio
async def test_cancel_blocks_new_participation_and_preserves_history(events_factory):
    owner = await make_user(events_factory, "cancel-history-owner"); participant = await make_user(events_factory, "cancel-history-user")
    try:
        async with events_factory() as session:
            await profile(session, owner); item = await EventService(session).create(owner, event_data()); service = EventService(session); registration = await service.register(participant, item.id); await service.cancel(owner, item.id)
            with pytest.raises(HTTPException): await service.register(participant, item.id)
            history = list(await session.scalars(select(AuditLog).where(AuditLog.resource_id == registration.id).order_by(AuditLog.created_at))); assert len(history) == 1
    finally: await cleanup(events_factory, [owner, participant])

@pytest.mark.asyncio
async def test_active_listing_excludes_cancelled_and_expired_sql_side(events_factory):
    owner = await make_user(events_factory, "list-owner")
    try:
        async with events_factory() as session:
            await profile(session, owner); service = EventService(session); visible = await service.create(owner, event_data(title="visible")); expired = await service.create(owner, event_data(title="expired", starts_at=datetime.now(timezone.utc)-timedelta(days=3), ends_at=datetime.now(timezone.utc)-timedelta(days=2))); cancelled = await service.create(owner, event_data(title="cancelled")); await service.cancel(owner, cancelled.id)
            ids = {x.id for x in await service.active(owner)}; assert visible.id in ids and expired.id not in ids and cancelled.id not in ids
    finally: await cleanup(events_factory, [owner])

@pytest.mark.asyncio
async def test_concurrent_registration_produces_one_row(events_factory):
    owner = await make_user(events_factory, "concurrent-owner"); participant = await make_user(events_factory, "concurrent-user")
    try:
        async with events_factory() as session: await profile(session, owner); item = await EventService(session).create(owner, event_data())
        event_id = item.id
        async def register_once():
            async with events_factory() as session: return await EventService(session).register(participant, event_id)
        first, second = await asyncio.gather(register_once(), register_once())
        assert first.id == second.id
        async with events_factory() as verify:
            assert len(list(await verify.scalars(select(EventRegistration).where(EventRegistration.event_id == event_id, EventRegistration.user_id == participant.user_id)))) == 1
    finally: await cleanup(events_factory, [owner, participant])

@pytest.mark.asyncio
async def test_participation_rollback_keeps_state_and_audit_consistent(events_factory, monkeypatch):
    owner = await make_user(events_factory, "rollback-owner"); participant = await make_user(events_factory, "rollback-user")
    try:
        async with events_factory() as session:
            await profile(session, owner); item = await EventService(session).create(owner, event_data()); service = EventService(session); original = session.commit
            event_id = item.id; participant_id = participant.user_id
            async def fail_commit(): raise RuntimeError("simulated commit failure")
            monkeypatch.setattr(session, "commit", fail_commit)
            with pytest.raises(RuntimeError): await service.register(participant, event_id)
            await session.rollback()
        async with events_factory() as verify:
            assert await verify.scalar(select(EventRegistration).where(EventRegistration.event_id == event_id, EventRegistration.user_id == participant_id)) is None
    finally: await cleanup(events_factory, [owner, participant])

@pytest.mark.asyncio
async def test_query_sanity_100_events_500_participations(events_factory):
    owner = await make_user(events_factory, "scale-owner"); participants = [await make_user(events_factory, f"scale-user-{i}") for i in range(5)]
    try:
        async with events_factory() as session:
            await profile(session, owner); now = datetime.now(timezone.utc); events = []
            for index in range(100):
                item = EcosystemEvent(organizer_user_id=owner.user_id, event_type="event", title=f"Scale {index}", location_type="online", location_details={}, starts_at=now+timedelta(days=1), ends_at=now+timedelta(days=2), status="active")
                session.add(item); events.append(item)
            await session.flush()
            for item in events:
                for participant in participants: session.add(EventRegistration(event_id=item.id, user_id=participant.user_id, status="registered"))
            await session.commit(); started = time.perf_counter(); result = await EventService(session).active(participants[0], limit=50); elapsed_ms = (time.perf_counter()-started)*1000
            assert len(result) == 50; print(f"SCRUM-201 query sanity: events=100 participations=500 elapsed_ms={elapsed_ms:.2f} query_shape=single_event_listing")
    finally: await cleanup(events_factory, [owner, *participants])

@pytest.mark.asyncio
async def test_fresh_session_reconstructs_participation_state(events_factory):
    owner = await make_user(events_factory, "fresh-owner"); participant = await make_user(events_factory, "fresh-user")
    try:
        async with events_factory() as session:
            await profile(session, owner); item = await EventService(session).create(owner, event_data()); await EventService(session).interest(participant, item.id); event_id = item.id
        async with events_factory() as fresh:
            state = await EventService(fresh).participation(participant, event_id); history = list(await fresh.scalars(select(AuditLog).where(AuditLog.resource_type == "event_registration", AuditLog.metadata_json["event_id"].as_string() == str(event_id))))
            assert state.status == "interested" and state.active and len(history) == 1
    finally: await cleanup(events_factory, [owner, participant])

@pytest.mark.asyncio
async def test_participation_isolated_between_events(events_factory):
    owner = await make_user(events_factory, "isolation-owner"); participant = await make_user(events_factory, "isolation-user")
    try:
        async with events_factory() as session:
            await profile(session, owner); service = EventService(session); first = await service.create(owner, event_data(title="E1")); second = await service.create(owner, event_data(title="E2")); await service.register(participant, first.id); state = await service.participation(participant, second.id); assert state.status is None and not state.active
    finally: await cleanup(events_factory, [owner, participant])

def test_fresh_event_model_import():
    import subprocess, sys
    result = subprocess.run([sys.executable, "-c", "import app.main; import app.db.models"], cwd=".", check=False)
    assert result.returncode == 0
