import uuid
import time
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import get_settings
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.models import InvestmentOpportunity, InvestmentOpportunityVersion, InvestorProfile
from app.modules.investment.opportunity_schemas import OpportunityCreate, OpportunityPatch
from app.modules.investment.opportunity_service import InvestmentOpportunityService
from app.modules.investment.schemas import ThesisCreate
from app.modules.investment.service import InvestorProfileService

@pytest_asyncio.fixture
async def opportunity_factory():
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection: await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose(); pytest.skip(f"PostgreSQL unavailable for SCRUM-200: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try: yield factory
    finally: await engine.dispose()

def actor(user_id, label): return AuthenticatedPrincipal(user_id=user_id, email=f"{label}-{user_id}@example.test", roles=(), provider="scrum200-test")

async def make_user(factory, label):
    user_id = uuid.uuid4(); item = actor(user_id, label)
    async with factory() as session: session.add(User(id=user_id, email=item.email)); await session.commit()
    return item

async def cleanup(factory, actors):
    ids = [x.user_id for x in actors]
    async with factory() as session:
        profiles = await session.scalars(select(InvestorProfile.id).where(InvestorProfile.user_id.in_(ids)))
        profile_ids = list(profiles)
        if profile_ids:
            opportunity_ids = list(await session.scalars(select(InvestmentOpportunity.id).where(InvestmentOpportunity.investor_profile_id.in_(profile_ids))))
            if opportunity_ids:
                await session.execute(update(InvestmentOpportunity).where(InvestmentOpportunity.id.in_(opportunity_ids)).values(current_version_id=None))
                await session.execute(delete(InvestmentOpportunityVersion).where(InvestmentOpportunityVersion.opportunity_id.in_(opportunity_ids)))
            await session.execute(delete(InvestmentOpportunity).where(InvestmentOpportunity.investor_profile_id.in_(profile_ids)))
        await session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(ids)))
        await session.execute(delete(InvestorProfile).where(InvestorProfile.user_id.in_(ids)))
        await session.execute(delete(User).where(User.id.in_(ids))); await session.commit()

async def create_profile(session, user): return await InvestorProfileService(session).create(user, ThesisCreate(sectors=["healthtech"]))

async def create_published(session, owner, **kwargs):
    data = {"title":"Opportunity", "description":"Description", "opportunity_type":"PROGRAM", "status":"PUBLISHED", **kwargs}
    return await InvestmentOpportunityService(session).create(owner, OpportunityCreate(**data))

@pytest.mark.asyncio
async def test_versioned_lifecycle_history_close_and_cross_user_denial(opportunity_factory):
    owner = await make_user(opportunity_factory, "owner"); other = await make_user(opportunity_factory, "other")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner)
            service = InvestmentOpportunityService(session)
            first = await service.create(owner, OpportunityCreate(title="Health", description="V1", opportunity_type="PROGRAM", criteria={"sectors":["healthtech"]}, status="PUBLISHED"))
            first_id = first.id; first_version_id = first.current_version_id
            second = await service.update(owner, first.id, OpportunityPatch(expected_version_id=first_version_id, description="V2"))
            second_version_id = second.current_version_id
            closed = await service.close(owner, first.id)
            versions = await service.versions(owner, first.id)
            assert second_version_id != first_version_id and closed.status == "CLOSED" and len(versions) == 3 and versions[0].description == "V1"
            with pytest.raises(HTTPException): await service.update(other, first.id, OpportunityPatch(expected_version_id=closed.current_version_id, description="bad"))
            with pytest.raises(HTTPException): await service.publish(owner, first.id)
        async with opportunity_factory() as fresh:
            current = await InvestmentOpportunityService(fresh).get(owner, first_id)
            assert current.status == "CLOSED" and current.description == "V2"
    finally: await cleanup(opportunity_factory, [owner, other])

@pytest.mark.asyncio
async def test_active_listing_is_sql_filtered_and_deadline_expires(opportunity_factory):
    owner = await make_user(opportunity_factory, "list")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); service = InvestmentOpportunityService(session)
            valid = await service.create(owner, OpportunityCreate(title="Valid", description="x", opportunity_type="PROGRAM", status="PUBLISHED"))
            await service.create(owner, OpportunityCreate(title="Expired", description="x", opportunity_type="PROGRAM", status="PUBLISHED", application_deadline=datetime.now(timezone.utc)-timedelta(days=1)))
            items = await service.active(owner); assert valid.id in [x.id for x in items] and all(x.application_deadline is None or x.application_deadline >= datetime.now(timezone.utc) for x in items)
    finally: await cleanup(opportunity_factory, [owner])

def test_opportunity_input_keeps_optional_criteria_explicit():
    item = OpportunityCreate(title="x", description="y", opportunity_type="PROGRAM")
    assert item.criteria == {} and item.application_deadline is None

@pytest.mark.asyncio
async def test_partial_create_preserves_missing_fields(opportunity_factory):
    owner = await make_user(opportunity_factory, "partial")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); item = await create_published(session, owner)
            assert item.criteria == {} and item.application_deadline is None and item.visibility == "AUTHENTICATED"
    finally: await cleanup(opportunity_factory, [owner])

@pytest.mark.asyncio
async def test_criteria_update_preserves_omitted_description(opportunity_factory):
    owner = await make_user(opportunity_factory, "criteria")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); first = await create_published(session, owner, description="keep", criteria={"sectors":["healthtech"]})
            updated = await InvestmentOpportunityService(session).update(owner, first.id, OpportunityPatch(expected_version_id=first.current_version_id, criteria={"stages":["seed"]}))
            assert updated.description == "keep" and updated.criteria == {"stages":["seed"]}
    finally: await cleanup(opportunity_factory, [owner])

@pytest.mark.asyncio
async def test_explicit_nullable_deadline_clear_creates_snapshot(opportunity_factory):
    owner = await make_user(opportunity_factory, "clear")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); first = await create_published(session, owner, application_deadline=datetime.now(timezone.utc)+timedelta(days=5))
            updated = await InvestmentOpportunityService(session).update(owner, first.id, OpportunityPatch(expected_version_id=first.current_version_id, application_deadline=None))
            history = await InvestmentOpportunityService(session).versions(owner, first.id)
            assert updated.application_deadline is None and history[0].application_deadline is not None
    finally: await cleanup(opportunity_factory, [owner])

@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["description", "criteria", "application_deadline"])
async def test_closed_rejects_all_unrelated_patch_shapes(opportunity_factory, field):
    owner = await make_user(opportunity_factory, f"terminal-{field}")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); first = await create_published(session, owner); closed = await InvestmentOpportunityService(session).close(owner, first.id)
            value = "attempt" if field == "description" else ({"x":1} if field == "criteria" else None)
            with pytest.raises(HTTPException) as error: await InvestmentOpportunityService(session).update(owner, first.id, OpportunityPatch(expected_version_id=closed.current_version_id, **{field:value}))
            assert error.value.status_code == 409
    finally: await cleanup(opportunity_factory, [owner])

@pytest.mark.asyncio
async def test_exact_historical_version_retrieval(opportunity_factory):
    owner = await make_user(opportunity_factory, "exact")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); service = InvestmentOpportunityService(session); first = await create_published(session, owner, description="V1")
            first_id = first.id; first_version_id = first.current_version_id
            second = await service.update(owner, first.id, OpportunityPatch(expected_version_id=first_version_id, description="V2"))
            second_version_id = second.current_version_id
            history = await service.versions(owner, first.id)
            assert [x.id for x in history] == [first_version_id, second_version_id] and [x.description for x in history] == ["V1", "V2"]
    finally: await cleanup(opportunity_factory, [owner])

@pytest.mark.asyncio
async def test_cross_user_close_and_history_are_denied(opportunity_factory):
    owner = await make_user(opportunity_factory, "history-owner"); other = await make_user(opportunity_factory, "history-other")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); item = await create_published(session, owner); service = InvestmentOpportunityService(session)
            with pytest.raises(HTTPException): await service.close(other, item.id)
            with pytest.raises(HTTPException): await service.versions(other, item.id)
    finally: await cleanup(opportunity_factory, [owner, other])

@pytest.mark.asyncio
async def test_identical_update_is_noop(opportunity_factory):
    owner = await make_user(opportunity_factory, "noop")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); service = InvestmentOpportunityService(session); first = await create_published(session, owner, criteria={"sectors":["healthtech"]})
            same = await service.update(owner, first.id, OpportunityPatch(expected_version_id=first.current_version_id, criteria={"sectors":["healthtech"]}))
            assert same.current_version_id == first.current_version_id and len(await service.versions(owner, first.id)) == 1
    finally: await cleanup(opportunity_factory, [owner])

@pytest.mark.asyncio
async def test_stale_concurrent_update_is_rejected(opportunity_factory):
    owner = await make_user(opportunity_factory, "concurrency")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); first = await create_published(session, owner)
        async with opportunity_factory() as one, opportunity_factory() as two:
            service_one = InvestmentOpportunityService(one); service_two = InvestmentOpportunityService(two)
            current_one = await service_one.get(owner, first.id); current_two = await service_two.get(owner, first.id)
            updated = await service_one.update(owner, first.id, OpportunityPatch(expected_version_id=current_one.current_version_id, description="A"))
            with pytest.raises(HTTPException) as error: await service_two.update(owner, first.id, OpportunityPatch(expected_version_id=current_two.current_version_id, criteria={"stages":["seed"]}))
            assert error.value.status_code == 409 and updated.description == "A"
    finally: await cleanup(opportunity_factory, [owner])

@pytest.mark.asyncio
async def test_failed_version_creation_rolls_back(opportunity_factory, monkeypatch):
    owner = await make_user(opportunity_factory, "rollback")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); service = InvestmentOpportunityService(session); first = await create_published(session, owner)
            first_id = first.id; first_version_id = first.current_version_id
            original = service._new_version
            async def fail_after_insert(item, actor, values, number):
                await original(item, actor, values, number); raise RuntimeError("simulated lifecycle failure")
            monkeypatch.setattr(service, "_new_version", fail_after_insert)
            with pytest.raises(RuntimeError): await service.update(owner, first_id, OpportunityPatch(expected_version_id=first_version_id, description="uncommitted"))
            await session.rollback()
        async with opportunity_factory() as fresh:
            current = await InvestmentOpportunityService(fresh).get(owner, first_id); history = await InvestmentOpportunityService(fresh).versions(owner, first_id)
            assert current.current_version_id == first_version_id and current.description == "Description" and len(history) == 1
    finally: await cleanup(opportunity_factory, [owner])

@pytest.mark.asyncio
async def test_cross_opportunity_current_pointer_is_rejected(opportunity_factory):
    owner = await make_user(opportunity_factory, "integrity")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); one = await create_published(session, owner); two = await create_published(session, owner)
            session.add(InvestmentOpportunity(id=uuid.uuid4(), investor_profile_id=one.investor_profile_id, current_version_id=two.current_version_id, title="bad", description="bad", opportunity_type="PROGRAM"))
            with pytest.raises(Exception): await session.flush()
            await session.rollback()
    finally: await cleanup(opportunity_factory, [owner])

@pytest.mark.asyncio
async def test_active_period_matrix(opportunity_factory):
    owner = await make_user(opportunity_factory, "periods")
    try:
        async with opportunity_factory() as session:
            await create_profile(session, owner); service = InvestmentOpportunityService(session)
            visible = await create_published(session, owner, title="visible")
            future = await create_published(session, owner, title="future", application_deadline=datetime.now(timezone.utc)+timedelta(days=2))
            expired = await create_published(session, owner, title="expired", application_deadline=datetime.now(timezone.utc)-timedelta(days=2))
            closed = await create_published(session, owner, title="closed"); await service.close(owner, closed.id)
            result = await service.active(owner); ids = {x.id for x in result}
            assert visible.id in ids and future.id in ids and expired.id not in ids and closed.id not in ids
    finally: await cleanup(opportunity_factory, [owner])

@pytest.mark.asyncio
async def test_active_listing_query_sanity_with_500_mixed_opportunities(opportunity_factory):
    owners = [await make_user(opportunity_factory, f"scale-{index}") for index in range(5)]
    try:
        async with opportunity_factory() as session:
            profiles = [await create_profile(session, owner) for owner in owners]
            now = datetime.now(timezone.utc); opportunities = []; versions = []
            for index in range(500):
                status = "CLOSED" if index % 4 == 0 else "PUBLISHED"
                deadline = now - timedelta(days=1) if index % 5 == 0 else (now + timedelta(days=2) if index % 7 == 0 else None)
                item = InvestmentOpportunity(investor_profile_id=profiles[index % 5].id, title=f"scale-{index}", description="scale", opportunity_type="PROGRAM", criteria={"index":index}, visibility="AUTHENTICATED", status=status, application_deadline=deadline, published_at=now)
                session.add(item); opportunities.append(item)
            await session.flush()
            for item in opportunities:
                version = InvestmentOpportunityVersion(opportunity_id=item.id, version_number=1, title=item.title, description=item.description, opportunity_type=item.opportunity_type, criteria=item.criteria, visibility=item.visibility, status=item.status, application_deadline=item.application_deadline, published_at=item.published_at, created_by_user_id=owners[0].user_id)
                session.add(version); versions.append(version)
            await session.flush()
            for item, version in zip(opportunities, versions): item.current_version_id = version.id
            await session.commit()
            started = time.perf_counter(); result = await InvestmentOpportunityService(session).active(owners[0], limit=50, offset=0); elapsed_ms = (time.perf_counter() - started) * 1000
            assert len(result) <= 50 and all(item.status == "PUBLISHED" and (item.application_deadline is None or item.application_deadline >= now) for item in result)
            print(f"SCRUM-200 query sanity: 500 rows, page=50, elapsed_ms={elapsed_ms:.2f}, query_shape=single_join")
    finally: await cleanup(opportunity_factory, owners)
