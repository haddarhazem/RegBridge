import asyncio
import time
import uuid
from datetime import datetime
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import get_settings
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.models import InvestorProfile
from app.modules.investment.schemas import ThesisCreate
from app.modules.investment.service import InvestorProfileService
from app.modules.network.models import ContactConsent, ContactPoint, ContactRequest
from app.modules.network.schemas import ContactAccept, ContactPointCreate, ContactRequestCreate
from app.modules.network.service import ContactRequestService
from app.modules.projects.models import Project, ProjectMember

@pytest_asyncio.fixture
async def contact_factory():
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection: await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose(); pytest.skip(f"PostgreSQL unavailable for SCRUM-202: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try: yield factory
    finally: await engine.dispose()

def actor(user_id, label): return AuthenticatedPrincipal(user_id=user_id, email=f"{label}-{user_id}@example.test", roles=(), provider="scrum202-test")

async def user(factory, label):
    user_id = uuid.uuid4(); result = actor(user_id, label)
    async with factory() as session: session.add(User(id=user_id, email=result.email)); await session.commit()
    return result

async def profile(session, actor): return await InvestorProfileService(session).create(actor, ThesisCreate(sectors=["healthtech"]))

async def project(session, owner, name="Startup"):
    item = Project(owner_user_id=owner.user_id, project_type="existing_startup", display_name=name, raw_description="startup", visibility="private", confirmed_fields={}); session.add(item); await session.flush(); session.add(ProjectMember(project_id=item.id, user_id=owner.user_id, member_role="owner", status="active")); await session.commit(); return item

async def cleanup(factory, actors):
    ids = [item.user_id for item in actors]
    async with factory() as session:
        project_ids = select(Project.id).where(Project.owner_user_id.in_(ids)); profile_ids = select(InvestorProfile.id).where(InvestorProfile.user_id.in_(ids))
        request_ids = select(ContactRequest.id).where(or_(ContactRequest.requester_user_id.in_(ids), and_target := (ContactRequest.target_type == "project") & ContactRequest.target_id.in_(project_ids), (ContactRequest.target_type == "investor_profile") & ContactRequest.target_id.in_(profile_ids), ContactRequest.source_project_id.in_(project_ids)))
        await session.execute(delete(ContactConsent).where(ContactConsent.request_id.in_(request_ids)))
        await session.execute(delete(ContactRequest).where(ContactRequest.id.in_(request_ids)))
        await session.execute(delete(ContactPoint).where(ContactPoint.owner_user_id.in_(ids)))
        await session.execute(delete(AuditLog).where(or_(AuditLog.actor_user_id.in_(ids), AuditLog.project_id.in_(project_ids))))
        await session.execute(delete(ProjectMember).where(ProjectMember.project_id.in_(project_ids))); await session.execute(delete(Project).where(Project.id.in_(project_ids)))
        await session.execute(delete(InvestorProfile).where(InvestorProfile.user_id.in_(ids))); await session.execute(delete(User).where(User.id.in_(ids))); await session.commit()

async def setup(factory):
    investor = await user(factory, "investor"); startup = await user(factory, "startup"); third = await user(factory, "third")
    async with factory() as session:
        investor_profile = await profile(session, investor); startup_project = await project(session, startup); service = ContactRequestService(session)
        email = await service.create_point(startup, ContactPointCreate(channel="EMAIL", value="founder@example.test", project_id=startup_project.id)); website = await service.create_point(startup, ContactPointCreate(channel="WEBSITE", value="https://startup.example.test", project_id=startup_project.id))
        investor_email = await service.create_point(investor, ContactPointCreate(channel="EMAIL", value="investor@example.test"))
        request = await service.create(investor, ContactRequestCreate(target_type="project", target_id=startup_project.id, message="Hello"))
        return investor, startup, third, investor_profile.id, startup_project.id, email.id, website.id, investor_email.id, request.id

@pytest.mark.asyncio
async def test_investor_to_startup_pending_hides_contacts_and_message(contact_factory):
    data = await setup(contact_factory)
    try:
        investor, startup, _, _, project_id, email_id, _, _, request_id = data
        async with contact_factory() as session:
            service = ContactRequestService(session); request = await service.list(investor); disclosure = await service.disclose(investor, request_id) if False else None
            assert request[0].status == "pending" and request[0].message == "Hello"
            with pytest.raises(HTTPException): await service.disclose(investor, request_id)
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_accept_reveals_only_explicit_channel(contact_factory):
    data = await setup(contact_factory); investor, startup, third, _, project_id, email_id, website_id, _, request_id = data
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session); accepted = await service.accept(startup, request_id, ContactAccept(contact_point_ids=[email_id])); disclosure = await service.disclose(investor, request_id)
            assert accepted.status == "accepted" and disclosure.contacts == [{"channel":"EMAIL","value":"founder@example.test"}]
            assert await session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == investor.user_id)) is None
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_partial_consent_and_revocation_are_scoped(contact_factory):
    data = await setup(contact_factory); investor, startup, _, _, _, email_id, website_id, _, request_id = data
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session); await service.accept(startup, request_id, ContactAccept(contact_point_ids=[email_id, website_id])); disclosure = await service.disclose(investor, request_id); assert len(disclosure.contacts) == 2
            consent = await session.scalar(select(ContactConsent).where(ContactConsent.request_id == request_id, ContactConsent.contact_point_id == email_id, ContactConsent.status == "active")); await service.revoke(startup, consent.id)
            disclosure = await service.disclose(investor, request_id); assert disclosure.contacts == [{"channel":"WEBSITE","value":"https://startup.example.test"}]
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_wrong_recipient_accept_refuse_and_contact_idor_denied(contact_factory):
    data = await setup(contact_factory); investor, startup, third, _, _, email_id, _, _, request_id = data
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session)
            with pytest.raises(HTTPException): await service.accept(third, request_id, ContactAccept(contact_point_ids=[email_id]))
            with pytest.raises(HTTPException): await service.refuse(third, request_id)
            with pytest.raises(HTTPException): await service.disclose(third, request_id)
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_refusal_discloses_nothing_and_is_idempotent(contact_factory):
    data = await setup(contact_factory); investor, startup, third, *_rest = data; request_id = data[-1]
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session); first = await service.refuse(startup, request_id); second = await service.refuse(startup, request_id); assert first.status == second.status == "declined"
            with pytest.raises(HTTPException): await service.disclose(investor, request_id)
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_duplicate_pending_is_idempotent_and_self_request_rejected(contact_factory):
    data = await setup(contact_factory); investor, startup, third, *_ = data; project_id = data[4]
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session); second = await service.create(investor, ContactRequestCreate(target_type="project", target_id=project_id)); assert second.id == data[-1]
            with pytest.raises(HTTPException): await service.create(startup, ContactRequestCreate(target_type="project", target_id=project_id))
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_new_contact_point_does_not_inherit_old_consent(contact_factory):
    data = await setup(contact_factory); investor, startup, third, *_ = data; email_id, request_id = data[5], data[-1]
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session); await service.accept(startup, request_id, ContactAccept(contact_point_ids=[email_id])); new_point = await service.create_point(startup, ContactPointCreate(channel="WEBSITE", value="https://new.example.test", project_id=data[4])); disclosure = await service.disclose(investor, request_id); assert all(item["value"] != "https://new.example.test" for item in disclosure.contacts)
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_startup_to_investor_direction_and_project_isolation(contact_factory):
    investor = await user(contact_factory, "direction-investor"); startup = await user(contact_factory, "direction-startup"); other = await user(contact_factory, "direction-other")
    try:
        async with contact_factory() as session:
            investor_profile = await profile(session, investor); first = await project(session, startup, "P1"); second = await project(session, startup, "P2"); point = await ContactRequestService(session).create_point(investor, ContactPointCreate(channel="EMAIL", value="investor@example.test")); request = await ContactRequestService(session).create(startup, ContactRequestCreate(target_type="investor_profile", target_id=investor_profile.id, source_project_id=first.id)); await ContactRequestService(session).accept(investor, request.id, ContactAccept(contact_point_ids=[point.id])); disclosure = await ContactRequestService(session).disclose(startup, request.id); assert disclosure.contacts[0]["channel"] == "EMAIL"
            second_request = await ContactRequestService(session).create(startup, ContactRequestCreate(target_type="investor_profile", target_id=investor_profile.id, source_project_id=second.id))
            assert second_request.id != request.id
            with pytest.raises(HTTPException): await ContactRequestService(session).disclose(startup, second_request.id)
    finally: await cleanup(contact_factory, [investor, startup, other])

@pytest.mark.asyncio
async def test_acceptance_has_no_sharing_grant_or_project_access_side_effect(contact_factory):
    data = await setup(contact_factory); investor, startup, third, *_ = data; request_id, email_id = data[-1], data[5]
    try:
        async with contact_factory() as session:
            await ContactRequestService(session).accept(startup, request_id, ContactAccept(contact_point_ids=[email_id])); from app.modules.sharing.models import InvestorShareGrant
            assert await session.scalar(select(InvestorShareGrant).where(InvestorShareGrant.recipient_user_id == investor.user_id)) is None
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_accept_is_idempotent_and_rollback_preserves_pending(contact_factory, monkeypatch):
    data = await setup(contact_factory); investor, startup, third, *_ = data; request_id, email_id = data[-1], data[5]
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session); first = await service.accept(startup, request_id, ContactAccept(contact_point_ids=[email_id])); second = await service.accept(startup, request_id, ContactAccept(contact_point_ids=[email_id])); assert first.status == second.status == "accepted"
        data2 = await setup(contact_factory); request2 = data2[-1]
        async with contact_factory() as session:
            service = ContactRequestService(session); original = session.commit
            async def fail(): raise RuntimeError("simulated commit failure")
            monkeypatch.setattr(session, "commit", fail)
            with pytest.raises(RuntimeError): await service.accept(data2[1], request2, ContactAccept())
            await session.rollback()
        async with contact_factory() as verify: assert (await verify.scalar(select(ContactRequest).where(ContactRequest.id == request2))).status == "pending"
        await cleanup(contact_factory, list(data2[:3]))
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_concurrent_accepts_have_one_terminal_request(contact_factory):
    data = await setup(contact_factory); investor, startup, third, *_ = data; request_id, email_id = data[-1], data[5]
    try:
        async def accept_once():
            async with contact_factory() as session: return await ContactRequestService(session).accept(startup, request_id, ContactAccept(contact_point_ids=[email_id]))
        first, second = await asyncio.gather(accept_once(), accept_once()); assert first.status == second.status == "accepted"
        async with contact_factory() as session: assert len(list(await session.scalars(select(ContactConsent).where(ContactConsent.request_id == request_id, ContactConsent.status == "active")))) == 1
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_cross_request_consent_is_not_reused(contact_factory):
    data = await setup(contact_factory); investor, startup, third, _, project_id, email_id, _, _, request_id = data
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session)
            await service.accept(startup, request_id, ContactAccept(contact_point_ids=[email_id]))
            second = await service.create(investor, ContactRequestCreate(target_type="project", target_id=project_id))
            assert second.id != request_id
            with pytest.raises(HTTPException): await service.disclose(investor, second.id)
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_cross_user_contact_point_binding_is_denied(contact_factory):
    data = await setup(contact_factory); investor, startup, third, _, _, email_id, _, investor_email_id, request_id = data
    try:
        async with contact_factory() as session:
            with pytest.raises(HTTPException):
                await ContactRequestService(session).accept(startup, request_id, ContactAccept(contact_point_ids=[investor_email_id]))
            assert (await session.scalar(select(ContactRequest).where(ContactRequest.id == request_id))).status == "pending"
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_revoke_is_idempotent_and_post_revoke_read_is_denied(contact_factory):
    data = await setup(contact_factory); investor, startup, third, _, _, email_id, _, _, request_id = data
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session); await service.accept(startup, request_id, ContactAccept(contact_point_ids=[email_id]))
            consent = await session.scalar(select(ContactConsent).where(ContactConsent.request_id == request_id, ContactConsent.status == "active"))
            consent_id = consent.id
            first = await service.revoke(startup, consent.id); second = await service.revoke(startup, consent.id)
            assert first.status == second.status == "revoked"
            assert (await service.disclose(investor, request_id)).contacts == []
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_revoke_rollback_preserves_active_consent(contact_factory, monkeypatch):
    data = await setup(contact_factory); investor, startup, third, _, _, email_id, _, _, request_id = data
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session); await service.accept(startup, request_id, ContactAccept(contact_point_ids=[email_id]))
            consent = await session.scalar(select(ContactConsent).where(ContactConsent.request_id == request_id, ContactConsent.status == "active"))
            consent_id = consent.id
            async def fail(): raise RuntimeError("simulated revoke commit failure")
            monkeypatch.setattr(session, "commit", fail)
            with pytest.raises(RuntimeError): await service.revoke(startup, consent_id)
            await session.rollback()
        async with contact_factory() as verify:
            assert (await verify.scalar(select(ContactConsent).where(ContactConsent.id == consent_id))).status == "active"
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_concurrent_accept_and_refuse_have_one_consistent_terminal_state(contact_factory):
    data = await setup(contact_factory); investor, startup, third, _, _, email_id, _, _, request_id = data
    try:
        async def accept_once():
            async with contact_factory() as session:
                try: return ("accepted", await ContactRequestService(session).accept(startup, request_id, ContactAccept(contact_point_ids=[email_id])))
                except HTTPException as exc: return (f"http_{exc.status_code}", None)
        async def refuse_once():
            async with contact_factory() as session:
                try: return ("refused", await ContactRequestService(session).refuse(startup, request_id))
                except HTTPException as exc: return (f"http_{exc.status_code}", None)
        results = await asyncio.gather(accept_once(), refuse_once())
        async with contact_factory() as session:
            request = await session.scalar(select(ContactRequest).where(ContactRequest.id == request_id))
            consents = list((await session.scalars(select(ContactConsent).where(ContactConsent.request_id == request_id, ContactConsent.status == "active"))).all())
            assert request.status in {"accepted", "declined"}
            assert not (request.status == "declined" and consents)
            assert sum(item[0] in {"accepted", "refused"} for item in results) == 1
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_acceptance_keeps_private_project_and_related_permissions_unchanged(contact_factory):
    data = await setup(contact_factory); investor, startup, third, _, project_id, email_id, _, _, request_id = data
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session); await service.accept(startup, request_id, ContactAccept(contact_point_ids=[email_id]))
            project = await session.get(Project, project_id)
            assert project.visibility == "private"
            assert await session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == investor.user_id)) is None
            from app.modules.sharing.models import InvestorShareGrant
            assert await session.scalar(select(InvestorShareGrant).where(InvestorShareGrant.recipient_user_id == investor.user_id)) is None
    finally: await cleanup(contact_factory, list(data[:3]))

@pytest.mark.asyncio
async def test_two_hundred_requests_listing_and_disclosure_sanity(contact_factory):
    investor = await user(contact_factory, "bulk-investor"); startup = await user(contact_factory, "bulk-startup")
    projects = []; request_ids = []
    try:
        async with contact_factory() as session:
            await profile(session, investor)
            service = ContactRequestService(session)
            for index in range(200):
                item = await project(session, startup, f"Bulk-{index}")
                projects.append(item.id)
                if index == 0:
                    point = await service.create_point(startup, ContactPointCreate(channel="EMAIL", value="bulk@example.test", project_id=item.id))
                request = await service.create(investor, ContactRequestCreate(target_type="project", target_id=item.id, message=f"request-{index}"))
                request_ids.append(request.id)
            await service.accept(startup, request_ids[0], ContactAccept(contact_point_ids=[point.id]))
            await service.refuse(startup, request_ids[1])
            started = time.perf_counter(); outgoing = (await service.list(investor, limit=100, offset=0)) + (await service.list(investor, limit=100, offset=100)); outgoing_elapsed = time.perf_counter() - started
            started = time.perf_counter(); incoming = (await service.list(startup, limit=100, offset=0)) + (await service.list(startup, limit=100, offset=100)); incoming_elapsed = time.perf_counter() - started
            disclosure = await service.disclose(investor, request_ids[0])
            assert len(outgoing) == len(incoming) == 200
            assert disclosure.contacts == [{"channel": "EMAIL", "value": "bulk@example.test"}]
            assert outgoing_elapsed < 10 and incoming_elapsed < 10
            print(f"SCRUM202_BULK outgoing={outgoing_elapsed:.4f}s incoming={incoming_elapsed:.4f}s")
    finally: await cleanup(contact_factory, [investor, startup])

@pytest.mark.asyncio
async def test_request_listing_pagination_is_stable_and_value_free(contact_factory):
    data = await setup(contact_factory); investor, startup, third, *_ = data
    try:
        async with contact_factory() as session:
            service = ContactRequestService(session)
            second_project = await project(session, startup, "Pagination-2")
            await service.create(investor, ContactRequestCreate(target_type="project", target_id=second_project.id))
            page_one = await service.list(investor, limit=1, offset=0)
            page_two = await service.list(investor, limit=1, offset=1)
            assert len(page_one) == len(page_two) == 1
            assert page_one[0].id != page_two[0].id
            assert not hasattr(page_one[0], "value")
    finally: await cleanup(contact_factory, list(data[:3]))
