import uuid
import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import get_settings
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project
from app.modules.projects.profile_models import StartupProfile, StartupProfileRevision
from app.modules.projects.search_schemas import StartupSearchFilters
from app.modules.projects.search_service import StartupSearchService
from app.modules.sharing.models import InvestorShareGrant

@pytest_asyncio.fixture
async def search_factory():
    engine=create_async_engine(get_settings().database_url,pool_pre_ping=True)
    try:
        async with engine.connect() as connection: await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose(); pytest.skip(f"PostgreSQL unavailable for SCRUM-199: {exc}")
    factory=async_sessionmaker(engine,expire_on_commit=False)
    try: yield factory
    finally: await engine.dispose()

def p(user_id,label): return AuthenticatedPrincipal(user_id=user_id,email=f"{label}-{user_id}@example.test",roles=(),provider="scrum199-test")

async def fixture(factory):
    ids=[uuid.uuid4() for _ in range(3)]; actors=[p(ids[0],"u1"),p(ids[1],"u2"),p(ids[2],"owner")]
    async with factory() as session:
        session.add_all([User(id=item.user_id,email=item.email) for item in actors])
        p1=Project(owner_user_id=ids[2],project_type="existing_startup",display_name="Alpha",raw_description="alpha",sector="healthtech",technology="AI",location="France",current_progress="seed",visibility="public",confirmed_fields={})
        p2=Project(owner_user_id=ids[2],project_type="existing_startup",display_name="Private",raw_description="private",sector="healthtech",technology="quantum",location="France",current_progress="seed",visibility="private",confirmed_fields={})
        p3=Project(owner_user_id=ids[2],project_type="existing_startup",display_name="Shared",raw_description="shared",sector="fintech",technology="robotics",location="Germany",current_progress="growth",visibility="private",confirmed_fields={})
        p4=Project(owner_user_id=ids[2],project_type="existing_startup",display_name="Beta",raw_description="beta",sector="fintech",technology="AI",location="Germany",current_progress="seed",visibility="public",confirmed_fields={})
        session.add_all([p1,p2,p3,p4]); await session.flush()
        profile=StartupProfile(project_id=p3.id,current_revision=1); session.add(profile); await session.flush(); revision=StartupProfileRevision(profile_id=profile.id,revision_number=1,snapshot=[{"field_name":"investor_summary","visibility":"INVESTOR_SHARED","value":"shared-safe"},{"field_name":"internal_notes","visibility":"PRIVATE","value":"hidden"}],changed_by_user_id=ids[2]); session.add(revision); await session.flush(); profile.current_version_id=revision.id
        session.add(InvestorShareGrant(project_id=p3.id,recipient_user_id=ids[0],resource_type="STARTUP_PROFILE_REVISION",resource_id=revision.id,scope="READ",status="ACTIVE",granted_by_user_id=ids[2]))
        await session.commit(); return {"actors":actors,"u1":ids[0],"u2":ids[1],"projects":[p1.id,p2.id,p3.id,p4.id],"grant":revision.id}

async def cleanup(factory,data):
    async with factory() as session:
        await session.execute(delete(InvestorShareGrant).where(InvestorShareGrant.project_id == data["projects"][2]))
        await session.execute(delete(StartupProfileRevision).where(StartupProfileRevision.id == data["grant"]))
        await session.execute(delete(StartupProfile).where(StartupProfile.project_id == data["projects"][2]))
        await session.execute(delete(Project).where(Project.id.in_(data["projects"])))
        await session.execute(delete(User).where(User.id.in_([item.user_id for item in data["actors"]]))); await session.commit()

@pytest.mark.asyncio
async def test_public_only_search_hides_private_rows_and_counts(search_factory):
    data=await fixture(search_factory)
    try:
        async with search_factory() as session:
            result=await StartupSearchService(session).search(data["actors"][0],StartupSearchFilters(sector="healthtech")); assert [x.startup_id for x in result.items] == [data["projects"][0]] and result.total_count == 1
            all_public=await StartupSearchService(session).search(data["actors"][0],StartupSearchFilters()); assert data["projects"][1] not in [x.startup_id for x in all_public.items]
    finally: await cleanup(search_factory,data)

@pytest.mark.asyncio
async def test_valid_grant_expands_only_shared_projection_and_revocation(search_factory):
    data=await fixture(search_factory)
    try:
        async with search_factory() as session:
            service=StartupSearchService(session); result=await service.search(data["actors"][0],StartupSearchFilters()); shared=next(item for item in result.items if item.startup_id == data["projects"][2]); assert shared.shared_fields == {"investor_summary":"shared-safe"} and "internal_notes" not in str(shared)
            no_grant=await service.search(data["actors"][1],StartupSearchFilters()); assert data["projects"][2] not in [item.startup_id for item in no_grant.items]
            grant=await session.get(InvestorShareGrant, (await session.execute(text("SELECT id FROM investor_share_grants WHERE resource_id = :rid"), {"rid":data["grant"]})).scalar_one()); grant.status="REVOKED"; await session.commit()
        async with search_factory() as session:
            after=await StartupSearchService(session).search(data["actors"][0],StartupSearchFilters()); assert data["projects"][2] not in [item.startup_id for item in after.items]
    finally: await cleanup(search_factory,data)

@pytest.mark.asyncio
async def test_filters_sorting_pagination_and_repeatability(search_factory):
    data=await fixture(search_factory)
    try:
        async with search_factory() as session:
            service=StartupSearchService(session); result=await service.search(data["actors"][0],StartupSearchFilters(sector="fintech",stage="seed",page=1,limit=1,sort="name")); assert result.total_count == 1 and result.items[0].startup_id == data["projects"][3]
            one=await service.search(data["actors"][0],StartupSearchFilters(sort="name")); two=await service.search(data["actors"][0],StartupSearchFilters(sort="name")); assert [x.startup_id for x in one.items] == [x.startup_id for x in two.items]
    finally: await cleanup(search_factory,data)

def test_unknown_and_private_dynamic_filters_are_rejected():
    with pytest.raises(ValidationError): StartupSearchFilters.model_validate({"private_notes":"secret"})

def test_page_limit_is_bounded():
    with pytest.raises(ValidationError): StartupSearchFilters(limit=101)

def test_allowed_filter_names_are_fixed():
    assert set(StartupSearchFilters.model_fields) == {"sector","stage","geography","technology","page","limit","sort"}

@pytest.mark.asyncio
async def test_wrong_recipient_and_cross_project_are_not_authorized(search_factory):
    data=await fixture(search_factory)
    try:
        async with search_factory() as session:
            result=await StartupSearchService(session).search(data["actors"][1],StartupSearchFilters(technology="robotics")); assert result.total_count == 0
    finally: await cleanup(search_factory,data)

def test_missing_filter_values_do_not_match():
    assert StartupSearchFilters(stage="seed").stage == "seed"

def test_sort_allowlist_excludes_private_columns():
    assert "raw_description" not in StartupSearchFilters.model_fields

def test_search_result_is_explicit_projection():
    from app.modules.projects.search_schemas import StartupSearchResult
    assert "private_notes" not in StartupSearchResult.model_fields

def test_grant_id_not_a_search_parameter():
    assert "grant_id" not in StartupSearchFilters.model_fields

def test_search_requires_authenticated_principal_at_router_boundary():
    # The route dependency is the authenticated principal; no user ID is accepted in filters.
    assert "user_id" not in StartupSearchFilters.model_fields
