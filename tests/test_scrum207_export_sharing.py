import io
import hashlib
import httpx

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from sqlalchemy import delete, select

from app.modules.audit import AuditLog
from app.main import app
from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.investment.brief_export_service import BriefExportShareService
from app.modules.investment.brief_schemas import BriefShareCreate, BriefVersionCreate, OpportunityBriefContent
from app.modules.investment.brief_service import OpportunityBriefService
from app.modules.investment.brief_models import InvestorOpportunityBriefRun
from app.modules.investment.brief_verification_models import BriefClaimVerification, BriefVerificationRun
from app.modules.sharing.models import InvestorShareGrant

from test_scrum203_matching import cleanup, make_fixture, make_user
from test_scrum205_verification import verification_factory


async def cleanup_brief_sharing(factory, actors, project_ids):
    actor_ids = [item.user_id for item in actors]
    async with factory() as session:
        run_ids = list((await session.scalars(select(InvestorOpportunityBriefRun.id).where(InvestorOpportunityBriefRun.investor_user_id.in_(actor_ids)))).all())
        verification_ids = list((await session.scalars(select(BriefVerificationRun.id).where(BriefVerificationRun.brief_run_id.in_(run_ids)))).all())
        await session.execute(delete(BriefClaimVerification).where(BriefClaimVerification.verification_run_id.in_(verification_ids)))
        await session.execute(delete(BriefVerificationRun).where(BriefVerificationRun.id.in_(verification_ids)))
        await session.commit()
    await cleanup(factory, actors, project_ids)


async def prepare_approved_version(session, actor, project_id, thesis_id):
    brief_service = OpportunityBriefService(session)
    brief = await brief_service.create(actor, project_id, thesis_id)
    version_one = await brief_service.current_version(actor, brief.id)
    assert (await brief_service.verify(actor, brief.id, version_one.id)).status == "VERIFIED"
    await brief_service.approve_version(actor, version_one.id)
    return brief, version_one


@pytest.mark.asyncio
async def test_approved_exact_version_exports_deterministic_pdf_and_shares(verification_factory):
    owner, startup, thesis_id, project_id, _ = await make_fixture(verification_factory)
    recipient = await make_user(verification_factory, "scrum207-recipient")
    try:
        async with verification_factory() as session:
            brief_service = OpportunityBriefService(session)
            brief, version_one = await prepare_approved_version(session, owner, project_id, thesis_id)
            public = OpportunityBriefContent.model_validate({key: version_one.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")})
            version_two = await brief_service.create_version(owner, brief.id, BriefVersionCreate(content=public))
            assert (await brief_service.verify(owner, brief.id, version_two.id)).status == "VERIFIED"
            await brief_service.approve_version(owner, version_two.id)
            version_three = await brief_service.create_version(owner, brief.id, BriefVersionCreate(content=public))
            assert version_three.status == "DRAFT"

            export_service = BriefExportShareService(session)
            with pytest.raises(HTTPException):
                await export_service.export_owner(owner, brief.id, version_three.id)
            owner_pdf, exported_number, owner_hash = await export_service.export_owner(owner, brief.id, version_two.id)
            repeat_pdf, _, repeat_hash = await export_service.export_owner(owner, brief.id, version_two.id)
            assert exported_number == 2 and owner_pdf == repeat_pdf and owner_hash == repeat_hash
            assert owner_hash == hashlib.sha256(owner_pdf).hexdigest()
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(owner_pdf)).pages)
            for heading in ("Investor Opportunity Brief", "1. Executive Summary", "2. Why This Startup Fits Your Thesis", "3. Key Investment Highlights", "4. Missing Information", "5. Disclaimer"):
                assert heading in text
            assert "fundraising_target: 300000" in text

            grant = await export_service.create_share(owner, brief.id, version_two.id, recipient.user_id)
            duplicate = await export_service.create_share(owner, brief.id, version_two.id, recipient.user_id)
            assert grant.id == duplicate.id and grant.scope == "READ" and grant.status == "ACTIVE"
            shared_grant, shared_run, shared_version = await export_service.shared_version(recipient, version_two.id)
            assert shared_grant.id == grant.id and shared_run.id == brief.id and shared_version.id == version_two.id
            recipient_pdf, recipient_number, recipient_hash = await export_service.export_shared(recipient, version_two.id)
            assert recipient_number == 2 and recipient_pdf == owner_pdf and recipient_hash == owner_hash

            with pytest.raises(HTTPException):
                await export_service.shared_version(recipient, version_one.id)
            with pytest.raises(HTTPException):
                await export_service.shared_version(recipient, version_three.id)
            with pytest.raises(HTTPException):
                await export_service.export_owner(recipient, brief.id, version_two.id)

            revoked = await export_service.revoke_share(owner, brief.id, version_two.id, grant.id)
            assert revoked.status == "REVOKED"
            with pytest.raises(HTTPException):
                await export_service.shared_version(recipient, version_two.id)
            with pytest.raises(HTTPException):
                await export_service.export_shared(recipient, version_two.id)

            audits = list((await session.scalars(select(AuditLog).where(AuditLog.resource_id == version_two.id))).all())
            assert {item.action for item in audits} >= {"EXPORT", "SHARE_CREATED", "SHARE_REVOKED"}
    finally:
        await cleanup_brief_sharing(verification_factory, [owner, startup, recipient], [project_id])


@pytest.mark.asyncio
async def test_scrum207_real_http_lifecycle_and_idor(verification_factory):
    owner, startup, thesis_id, project_id, _ = await make_fixture(verification_factory)
    recipient = await make_user(verification_factory, "scrum207-http-recipient")
    unrelated = await make_user(verification_factory, "scrum207-http-unrelated")

    async def override_session():
        async with verification_factory() as session:
            yield session

    async def request_as(principal, method, path, **kwargs):
        app.dependency_overrides[get_authenticated_principal] = lambda: principal
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    try:
        async with verification_factory() as session:
            service = OpportunityBriefService(session)
            brief, version_one = await prepare_approved_version(session, owner, project_id, thesis_id)
            content = OpportunityBriefContent.model_validate({key: version_one.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")})
            version_two = await service.create_version(owner, brief.id, BriefVersionCreate(content=content))
            await service.verify(owner, brief.id, version_two.id)
            await service.approve_version(owner, version_two.id)
            version_three = await service.create_version(owner, brief.id, BriefVersionCreate(content=content))

        app.dependency_overrides[get_session] = override_session
        base = f"/investment-briefs/{brief.id}/versions/{version_two.id}"
        owner_pdf = await request_as(owner, "GET", f"{base}/export.pdf")
        assert owner_pdf.status_code == 200
        assert owner_pdf.headers["content-type"].startswith("application/pdf")
        assert f"v2.pdf" in owner_pdf.headers["content-disposition"]
        assert owner_pdf.content.startswith(b"%PDF-")

        share = await request_as(owner, "POST", f"{base}/shares", json={"recipient_user_id": str(recipient.user_id), "scope": "READ"})
        duplicate = await request_as(owner, "POST", f"{base}/shares", json={"recipient_user_id": str(recipient.user_id), "scope": "READ"})
        assert share.status_code == 201 and duplicate.status_code == 201
        assert share.json()["id"] == duplicate.json()["id"]
        assert share.json()["version_id"] == str(version_two.id) and share.json()["scope"] == "READ"

        listing = await request_as(recipient, "GET", "/investment-briefs/shared-with-me")
        shared = await request_as(recipient, "GET", f"/investment-briefs/shared/{version_two.id}")
        recipient_pdf = await request_as(recipient, "GET", f"/investment-briefs/shared/{version_two.id}/export.pdf")
        assert listing.status_code == 200 and [item["version_id"] for item in listing.json()] == [str(version_two.id)]
        assert shared.status_code == 200 and shared.json()["version_id"] == str(version_two.id)
        assert set(shared.json()["content"]) == {"executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer"}
        assert recipient_pdf.status_code == 200 and recipient_pdf.content == owner_pdf.content

        for path in (
            f"/investment-briefs/{brief.id}/versions/{version_one.id}",
            f"/investment-briefs/{brief.id}/versions/{version_three.id}",
            f"/investment-briefs/shared/{version_one.id}",
            f"/investment-briefs/shared/{version_three.id}",
        ):
            assert (await request_as(recipient, "GET", path)).status_code in {404, 409}
        assert (await request_as(unrelated, "GET", f"/investment-briefs/shared/{version_two.id}")).status_code == 404
        assert (await request_as(unrelated, "GET", f"/investment-briefs/shared/{version_two.id}/export.pdf")).status_code == 404
        assert (await request_as(recipient, "POST", f"/investment-briefs/{brief.id}/versions/{version_two.id}/verify")).status_code == 404
        assert (await request_as(recipient, "POST", f"/investment-briefs/{brief.id}/versions/{version_two.id}/approve")).status_code == 404
        assert (await request_as(recipient, "POST", f"/investment-briefs/{brief.id}/versions/{version_two.id}/shares", json={"recipient_user_id": str(unrelated.user_id)})).status_code == 404

        revoke = await request_as(owner, "DELETE", f"{base}/shares/{share.json()['id']}")
        assert revoke.status_code == 200 and revoke.json()["status"] == "REVOKED"
        assert (await request_as(recipient, "GET", f"/investment-briefs/shared/{version_two.id}")).status_code == 404
        assert (await request_as(recipient, "GET", f"/investment-briefs/shared/{version_two.id}/export.pdf")).status_code == 404
        assert (await request_as(recipient, "GET", "/investment-briefs/shared-with-me")).json() == []
    finally:
        app.dependency_overrides.clear()
        await cleanup_brief_sharing(verification_factory, [owner, startup, recipient, unrelated], [project_id])
