import pytest
import httpx

from app.db.session import get_session
from app.main import app
from app.modules.identity.dependencies import get_authenticated_principal

from app.modules.investment.brief_service import OpportunityBriefService
from app.modules.investment.brief_schemas import BriefVersionCreate, OpportunityBriefContent
from app.modules.investment.matching_service import MatchingService

from test_scrum203_matching import cleanup, make_fixture, matching_factory


@pytest.mark.asyncio
async def test_investor_owner_lists_are_isolated_and_ordered(matching_factory):
    investor_a, startup_a, thesis_a, project_a, _ = await make_fixture(matching_factory, investor_label="owner-list-a")
    investor_b, startup_b, thesis_b, project_b, _ = await make_fixture(matching_factory, investor_label="owner-list-b")
    try:
        async with matching_factory() as session:
            match_a_one = await MatchingService(session).create(investor_a, project_a, thesis_a)
            match_a_two = await MatchingService(session).create(investor_a, project_a, thesis_a)
            match_b = await MatchingService(session).create(investor_b, project_b, thesis_b)

        async with matching_factory() as session:
            matches_a = await MatchingService(session).list_owned(investor_a, limit=10)
            matches_b = await MatchingService(session).list_owned(investor_b, limit=10)

        assert {item.id for item in matches_a} == {match_a_one.id, match_a_two.id}
        assert {item.id for item in matches_b} == {match_b.id}
        assert all(item.startup_project_id == project_a for item in matches_a)
        assert [(item.created_at, item.id) for item in matches_a] == sorted(
            ((item.created_at, item.id) for item in matches_a), reverse=True
        )
        assert all("startup_snapshot" not in item.result_summary and "report" not in item.result_summary for item in matches_a)
    finally:
        await cleanup(matching_factory, [investor_a, startup_a, investor_b, startup_b], [project_a, project_b])


@pytest.mark.asyncio
async def test_investor_match_owner_list_is_bounded_and_paginated(matching_factory):
    investor, startup, thesis, project, _ = await make_fixture(matching_factory, investor_label="owner-list-pagination")
    try:
        async with matching_factory() as session:
            runs = [await MatchingService(session).create(investor, project, thesis) for _ in range(3)]
            listed = await MatchingService(session).list_owned(investor, limit=2, offset=1)
        assert len(listed) == 2
        assert {item.id for item in listed}.issubset({run.id for run in runs})
    finally:
        await cleanup(matching_factory, [investor, startup], [project])


@pytest.mark.asyncio
async def test_investor_brief_owner_list_returns_latest_version_only(matching_factory):
    investor, startup, thesis, project, _ = await make_fixture(matching_factory, investor_label="owner-list-brief")
    try:
        async with matching_factory() as session:
            service = OpportunityBriefService(session)
            brief = await service.create(investor, project, thesis)
            current_one = await service.current_version(investor, brief.id)
            content = OpportunityBriefContent.model_validate({
                key: current_one.content[key]
                for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")
            })
            version_two = await service.create_version(
                investor,
                brief.id,
                BriefVersionCreate(content=content),
            )
            listed = await service.list_owned(investor, limit=10)

        assert len(listed) == 1
        assert listed[0].id == brief.id
        assert listed[0].current_version_id == version_two.id
        assert listed[0].current_version_number == 2
        assert listed[0].investor_thesis_version_id == thesis
        assert listed[0].verification_status in {"UNVERIFIED", "VERIFICATION_FAILED", "VERIFIED", "APPROVED"}
    finally:
        await cleanup(matching_factory, [investor, startup], [project])


@pytest.mark.asyncio
async def test_investor_owner_list_routes_do_not_cross_leak(matching_factory):
    investor_a, startup_a, thesis_a, project_a, _ = await make_fixture(matching_factory, investor_label="owner-list-http-a")
    investor_b, startup_b, thesis_b, project_b, _ = await make_fixture(matching_factory, investor_label="owner-list-http-b")

    async def override_session():
        async with matching_factory() as session:
            yield session

    async def request_as(principal, path):
        app.dependency_overrides[get_authenticated_principal] = lambda: principal
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path)

    try:
        async with matching_factory() as session:
            match_a = await MatchingService(session).create(investor_a, project_a, thesis_a)
            match_b = await MatchingService(session).create(investor_b, project_b, thesis_b)
            brief_a = await OpportunityBriefService(session).create(investor_a, project_a, thesis_a, matching_run_id=match_a.id)

        app.dependency_overrides[get_session] = override_session
        matches_a = await request_as(investor_a, "/investor/matches")
        matches_b = await request_as(investor_b, "/investor/matches")
        briefs_a = await request_as(investor_a, "/investor/briefs")
        briefs_b = await request_as(investor_b, "/investor/briefs")

        assert matches_a.status_code == matches_b.status_code == 200
        assert [item["id"] for item in matches_a.json()] == [str(match_a.id),]
        assert [item["id"] for item in matches_b.json()] == [str(match_b.id),]
        assert briefs_a.status_code == briefs_b.status_code == 200
        assert [item["id"] for item in briefs_a.json()] == [str(brief_a.id)]
        assert briefs_b.json() == []
        assert "startup_snapshot" not in matches_a.text
    finally:
        app.dependency_overrides.clear()
        await cleanup(matching_factory, [investor_a, startup_a, investor_b, startup_b], [project_a, project_b])
