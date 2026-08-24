import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.modules.investment.brief_schemas import BriefVersionCreate, OpportunityBriefContent
from app.modules.investment.brief_router import approve_brief_version, create_brief_version, get_current_brief_version, list_brief_versions, verify_brief_version
from app.modules.investment.brief_models import InvestorOpportunityBriefRun
from app.modules.investment.brief_service import OpportunityBriefService
from app.modules.investment.brief_verification_models import BriefClaimVerification, BriefVerificationRun

from test_scrum203_matching import cleanup, make_fixture, make_user
from test_scrum205_verification import verification_factory


async def cleanup_brief_versions(factory, actors, project_ids):
    actor_ids = [item.user_id for item in actors]
    async with factory() as session:
        run_ids = list((await session.scalars(select(InvestorOpportunityBriefRun.id).where(InvestorOpportunityBriefRun.investor_user_id.in_(actor_ids)))).all())
        verification_ids = list((await session.scalars(select(BriefVerificationRun.id).where(BriefVerificationRun.brief_run_id.in_(run_ids)))).all())
        await session.execute(delete(BriefClaimVerification).where(BriefClaimVerification.verification_run_id.in_(verification_ids)))
        await session.execute(delete(BriefVerificationRun).where(BriefVerificationRun.id.in_(verification_ids)))
        await session.commit()
    await cleanup(factory, actors, project_ids)


@pytest.mark.asyncio
async def test_brief_version_lifecycle_and_approval(verification_factory):
    investor, startup, version_id, project_id, _ = await make_fixture(verification_factory)
    try:
        async with verification_factory() as session:
            service = OpportunityBriefService(session)
            brief = await service.create(investor, project_id, version_id)
            first = await service.current_version(investor, brief.id)
            assert first.version_number == 1 and first.status == "DRAFT"

            verified_first = await service.verify(investor, brief.id, first.id)
            assert verified_first.status == "VERIFIED"

            first_public = OpportunityBriefContent.model_validate({key: first.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")})
            corrected = first_public.model_copy(update={"executive_summary": "Corrected wording based on the same frozen evidence."})
            second = await service.create_version(investor, brief.id, BriefVersionCreate(content=corrected))
            assert second.version_number == 2
            assert second.status == "DRAFT"
            assert second.verification_status == "UNVERIFIED"
            assert second.content.executive_summary != first_public.executive_summary

            with pytest.raises(HTTPException) as denied:
                await service.approve_version(investor, second.id)
            assert denied.value.status_code == 409

            verified_second = await service.verify(investor, brief.id, second.id)
            assert verified_second.status == "VERIFIED"
            approved = await service.approve_version(investor, second.id)
            assert approved.status == "APPROVED" and approved.approved

            history = await service.list_versions(investor, brief.id)
            assert [item.version_number for item in history] == [1, 2]
            assert history[0].content.executive_summary == first_public.executive_summary
            assert history[1].status == "APPROVED"

            third = await service.create_version(investor, brief.id, BriefVersionCreate(content=corrected))
            assert third.version_number == 3 and third.status == "DRAFT"
            history = await service.list_versions(investor, brief.id)
            assert history[1].status == "APPROVED"
    finally:
        await cleanup_brief_versions(verification_factory, [investor, startup], [project_id])


@pytest.mark.asyncio
async def test_corrected_unsupported_fact_cannot_be_approved(verification_factory):
    investor, startup, version_id, project_id, _ = await make_fixture(verification_factory)
    try:
        async with verification_factory() as session:
            service = OpportunityBriefService(session)
            brief = await service.create(investor, project_id, version_id)
            first = await service.current_version(investor, brief.id)
            public = {key: first.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")}
            public["investment_highlights"] = [*public["investment_highlights"], "customers: 12"]
            second = await service.create_version(investor, brief.id, BriefVersionCreate(content=OpportunityBriefContent.model_validate(public)))
            result = await service.verify(investor, brief.id, second.id)
            assert result.status == "VERIFICATION_FAILED"
            with pytest.raises(HTTPException):
                await service.approve_version(investor, second.id)
    finally:
        await cleanup_brief_versions(verification_factory, [investor, startup], [project_id])


@pytest.mark.asyncio
async def test_brief_version_authorization_and_idor(verification_factory):
    investor, startup, version_id, project_id, _ = await make_fixture(verification_factory)
    other = await make_user(verification_factory, "scrum206-other")
    try:
        async with verification_factory() as session:
            service = OpportunityBriefService(session)
            brief = await service.create(investor, project_id, version_id)
            version = await service.current_version(investor, brief.id)
            for operation in (
                lambda: service.list_versions(other, brief.id),
                lambda: service._authorized_version(other, version.id),
                lambda: service.create_version(other, brief.id, BriefVersionCreate(content=OpportunityBriefContent.model_validate({key: version.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")}))),
                lambda: service.approve_version(other, version.id),
            ):
                with pytest.raises(HTTPException) as denied:
                    await operation()
                assert denied.value.status_code == 404
    finally:
        await cleanup_brief_versions(verification_factory, [investor, startup, other], [project_id])


def test_brief_version_contract_rejects_missing_and_extra_sections():
    valid = {
        "executive_summary": "summary",
        "thesis_fit": ["sector: MATCH"],
        "investment_highlights": [],
        "missing_information": [],
        "disclaimer": "disclaimer",
    }
    with pytest.raises(Exception):
        OpportunityBriefContent.model_validate({key: value for key, value in valid.items() if key != "disclaimer"})
    with pytest.raises(Exception):
        OpportunityBriefContent.model_validate({**valid, "risk_analysis": "not allowed"})


@pytest.mark.asyncio
async def test_concurrent_version_creation_is_serialized(verification_factory):
    investor, startup, version_id, project_id, _ = await make_fixture(verification_factory)
    try:
        async with verification_factory() as session:
            service = OpportunityBriefService(session)
            brief = await service.create(investor, project_id, version_id)
            first = await service.current_version(investor, brief.id)
            public = OpportunityBriefContent.model_validate({key: first.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")})
            await service.create_version(investor, brief.id, BriefVersionCreate(content=public))

        async def create_one(text: str):
            async with verification_factory() as concurrent_session:
                return await OpportunityBriefService(concurrent_session).create_version(
                    investor,
                    brief.id,
                    BriefVersionCreate(content=public.model_copy(update={"executive_summary": text})),
                )

        created = await asyncio.gather(create_one("correction A"), create_one("correction B"))
        assert sorted(item.version_number for item in created) == [3, 4]
        assert len({item.id for item in created}) == 2
        async with verification_factory() as session:
            current = await OpportunityBriefService(session).current_version(investor, brief.id)
            assert current.version_number == 4
    finally:
        await cleanup_brief_versions(verification_factory, [investor, startup], [project_id])


@pytest.mark.asyncio
async def test_production_route_version_round_trip(verification_factory):
    investor, startup, version_id, project_id, _ = await make_fixture(verification_factory)
    try:
        async with verification_factory() as session:
            service = OpportunityBriefService(session)
            brief = await service.create(investor, project_id, version_id)
            first = await service.current_version(investor, brief.id)
            assert (await service.verify(investor, brief.id, first.id)).status == "VERIFIED"
            public = OpportunityBriefContent.model_validate({key: first.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")})
            second = await create_brief_version(brief.id, BriefVersionCreate(content=public), investor, session)
            assert second.version_number == 2 and second.status == "DRAFT"
            assert (await get_current_brief_version(brief.id, investor, session)).id == second.id
            assert [item.version_number for item in await list_brief_versions(brief.id, investor, session)] == [1, 2]
            assert (await verify_brief_version(brief.id, second.id, investor, session)).status == "VERIFIED"
            approved = await approve_brief_version(brief.id, second.id, investor, session)
            assert approved.status == "APPROVED"
            persisted = await get_current_brief_version(brief.id, investor, session)
            assert persisted.id == second.id and persisted.status == "APPROVED"
    finally:
        await cleanup_brief_versions(verification_factory, [investor, startup], [project_id])
