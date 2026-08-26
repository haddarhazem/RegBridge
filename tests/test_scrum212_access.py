import uuid

import pytest
import pytest_asyncio
import httpx
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import get_settings
from app.main import app
from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.audit import AuditLog
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember
from app.modules.projects.service import ProjectService
from app.modules.projects.schemas import IdeaProjectCreate
from app.modules.research.access_service import ResearchAccessService
from app.modules.research.service import ResearchService
from app.modules.research.models import (
    ResearchAccessRequest,
    ResearchDiscovery,
    ResearchDiscoveryVersion,
    ResearchExtractionRun,
    ResearchOutput,
    ResearchOutputVersion,
    ResearcherProfile,
)
from app.modules.research.schemas import ResearchAccessDecision, ResearchAccessRequestCreate
from app.modules.sharing.models import InvestorShareGrant


@pytest_asyncio.fixture
async def access_factory():
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def principal(user_id, email):
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="scrum212-test")


@pytest.mark.asyncio
async def test_scrum212_request_decisions_grants_and_revocation(access_factory):
    owner_id = uuid.uuid4(); requester_id = uuid.uuid4(); owner_email = f"scrum212-owner-{owner_id}@example.test"; requester_email = f"scrum212-requester-{requester_id}@example.test"; project_id = None; discovery_id = None
    async with access_factory() as session:
        session.add_all([User(id=owner_id, email=owner_email), User(id=requester_id, email=requester_email)]); await session.commit()
    try:
        async with access_factory() as session:
            project = await ProjectService(session).create_idea(principal(requester_id, requester_email), IdeaProjectCreate(display_name="Research requester")); project_id = project.id
            profile = ResearcherProfile(user_id=owner_id, scientific_domains=["engineering"]); session.add(profile); await session.flush()
            output = ResearchOutput(researcher_profile_id=profile.id, title="Research", authors=["Author"], rights_holder="Author", licence="CC-BY", visibility="private", rights_metadata_status="COMPLETE", publication_ready=True); session.add(output); await session.flush()
            document = Document(owner_user_id=owner_id, title="Research source", document_type="txt", classification="confidential", visibility="private", processing_status="uploaded"); session.add(document); await session.flush()
            document_version = DocumentVersion(document_id=document.id, version_number=1, original_filename="research.txt", storage_key=f"scrum212/{document.id}/v1", mime_type="text/plain", size_bytes=10, sha256="a" * 64, malware_scan_status="clean", uploaded_by_user_id=owner_id); session.add(document_version); await session.flush(); document.current_version_id = document_version.id
            output_version = ResearchOutputVersion(research_output_id=output.id, document_version_id=document_version.id, version_number=1, uploaded_by_user_id=owner_id, content_hash="b" * 64); session.add(output_version); await session.flush()
            extraction_run = ResearchExtractionRun(
                owner_user_id=owner_id, research_output_id=output.id,
                research_output_version_id=output_version.id,
                document_version_id=document_version.id, source_sha256="c" * 64,
                strategy="extractive_evidence_locked", strategy_version="v4",
                provider="deterministic", model="none", prompt_version="none",
                schema_version="v1", segmenter_version="v1", status="GENERATED",
                regbridge_abstract="safe abstract",
            )
            session.add(extraction_run); await session.flush()
            discovery = ResearchDiscovery(research_output_id=output.id, owner_user_id=owner_id); session.add(discovery); await session.flush(); discovery_id = discovery.id
            discovery_v1 = ResearchDiscoveryVersion(
                discovery_id=discovery.id, version_number=1,
                extraction_run_id=extraction_run.id,
                research_output_version_id=output_version.id,
                document_version_id=document_version.id, source_sha256="c" * 64,
                content={"fields": {"domains": ["public domain"], "research_problem": ["public problem"]}, "evidence": {"research_problem": [{"private_text": "SECRET PRIVATE EVIDENCE"}]}, "abstract": "private abstract"},
                visibility={"domains": "MATCHABLE", "research_problem": "PUBLIC", "abstract": "PRIVATE"},
                status="APPROVED", approved_by_user_id=owner_id,
            )
            discovery_v2 = ResearchDiscoveryVersion(
                discovery_id=discovery.id, version_number=2,
                extraction_run_id=extraction_run.id,
                research_output_version_id=output_version.id,
                document_version_id=document_version.id, source_sha256="c" * 64,
                content={"fields": {"domains": ["new version"]}, "evidence": {}, "abstract": "new"},
                visibility={"domains": "PRIVATE", "abstract": "PRIVATE"}, status="APPROVED", approved_by_user_id=owner_id,
            )
            session.add_all([discovery_v1, discovery_v2]); await session.commit()
            service = ResearchAccessService(session)
            request = await service.create(principal(requester_id, requester_email), ResearchAccessRequestCreate(research_output_id=output.id, research_output_version_id=output_version.id, requester_project_id=project_id, requested_scopes=["FULL_DOCUMENT_READ", "COLLABORATION"]))
            async def override_session():
                async with access_factory() as request_session:
                    yield request_session
            app.dependency_overrides[get_session] = override_session
            app.dependency_overrides[get_authenticated_principal] = lambda: principal(requester_id, requester_email)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                read_response = await client.get(f"/research/access-requests/{request.id}")
                assert read_response.status_code == 200 and read_response.json()["status"] == "PENDING"
            app.dependency_overrides[get_authenticated_principal] = lambda: principal(owner_id, owner_email)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                accept_response = await client.post(f"/research/access-requests/{request.id}/accept")
                assert accept_response.status_code == 200 and accept_response.json()["granted_scopes"] == ["FULL_DOCUMENT_READ", "COLLABORATION"]
            app.dependency_overrides.clear()
            app.dependency_overrides[get_session] = override_session
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                assert (await client.get(f"/research/access-requests/{request.id}")).status_code == 401
                app.dependency_overrides.clear()
                accepted = await session.get(ResearchAccessRequest, request.id)
                await session.refresh(accepted)
            assert accepted.status == "ACCEPTED" and set(accepted.granted_scopes) == {"FULL_DOCUMENT_READ", "COLLABORATION"}
            grants = (await session.scalars(select(InvestorShareGrant).where(InvestorShareGrant.request_id == request.id))).all()
            assert len(grants) == 2 and all(grant.resource_version_id == output_version.id for grant in grants)
            assert await service.has_scope(principal(requester_id, requester_email), output_id=output.id, output_version_id=output_version.id, scope="FULL_DOCUMENT_READ")
            await service.revoke(principal(owner_id, owner_email), request.id)
            assert not await service.has_scope(principal(requester_id, requester_email), output_id=output.id, output_version_id=output_version.id, scope="FULL_DOCUMENT_READ")
            actions = (await session.scalars(select(AuditLog.action).where(AuditLog.resource_id == request.id))).all()
            assert {"RESEARCH_ACCESS_REQUEST_CREATED", "RESEARCH_ACCESS_REQUEST_ACCEPTED", "RESEARCH_ACCESS_REQUEST_REVOKED"} <= set(actions)
            limited_request = await service.create(principal(requester_id, requester_email), ResearchAccessRequestCreate(research_output_id=output.id, research_output_version_id=output_version.id, requester_project_id=project_id, requested_scopes=["FULL_DOCUMENT_READ", "COLLABORATION"]))
            limited = await service.decide(principal(owner_id, owner_email), limited_request.id, "LIMITED", ResearchAccessDecision(granted_scopes=["COLLABORATION"]))
            assert limited.status == "LIMITED" and limited.granted_scopes == ["COLLABORATION"]
            assert not await service.has_scope(principal(requester_id, requester_email), output_id=output.id, output_version_id=output_version.id, scope="DISCOVERY_READ")
            assert not await service.has_scope(principal(requester_id, requester_email), output_id=output.id, output_version_id=output_version.id, scope="FULL_DOCUMENT_READ")
            with pytest.raises(HTTPException) as transition:
                await service.decide(principal(owner_id, owner_email), limited_request.id, "ACCEPTED", ResearchAccessDecision())
            assert transition.value.status_code == 409
            await service.revoke(principal(owner_id, owner_email), limited_request.id)
            refused_request = await service.create(principal(requester_id, requester_email), ResearchAccessRequestCreate(research_output_id=output.id, research_output_version_id=output_version.id, requester_project_id=project_id, requested_scopes=["COLLABORATION"]))
            refused = await service.decide(principal(owner_id, owner_email), refused_request.id, "REFUSED", ResearchAccessDecision())
            assert refused.status == "REFUSED" and refused.granted_scopes == []
            assert not (await session.scalars(select(InvestorShareGrant).where(InvestorShareGrant.request_id == refused.id))).all()

            # CONTACT is persisted as an explicit capability and never implies
            # discovery, document, collaboration, or private contact data.
            contact_request = await service.create(
                principal(requester_id, requester_email),
                ResearchAccessRequestCreate(
                    research_output_id=output.id,
                    research_output_version_id=output_version.id,
                    requester_project_id=project_id,
                    requested_scopes=["CONTACT"],
                ),
            )
            assert not await service.has_scope(principal(requester_id, requester_email), output_id=output.id, output_version_id=output_version.id, scope="CONTACT")
            contact = await service.decide(principal(owner_id, owner_email), contact_request.id, "ACCEPTED", ResearchAccessDecision())
            assert contact.status == "ACCEPTED" and contact.granted_scopes == ["CONTACT"]
            contact_actor = principal(requester_id, requester_email)
            async with access_factory() as fresh_session:
                fresh_contact = await fresh_session.get(ResearchAccessRequest, contact_request.id)
                assert fresh_contact.status == "ACCEPTED" and fresh_contact.granted_scopes == ["CONTACT"]
                assert await ResearchAccessService(fresh_session).has_scope(contact_actor, output_id=output.id, output_version_id=output_version.id, scope="CONTACT")
            assert not await service.has_scope(contact_actor, output_id=output.id, output_version_id=output_version.id, scope="DISCOVERY_READ")
            assert not await service.has_scope(contact_actor, output_id=output.id, output_version_id=output_version.id, scope="FULL_DOCUMENT_READ")
            assert not await service.has_scope(contact_actor, output_id=output.id, output_version_id=output_version.id, scope="COLLABORATION")
            assert not hasattr(output, "email") and not hasattr(output, "phone")
            contact_grants_before_revoke = (await session.scalars(select(InvestorShareGrant).where(InvestorShareGrant.request_id == contact_request.id))).all()
            assert len(contact_grants_before_revoke) == 1
            await service.revoke(principal(owner_id, owner_email), contact_request.id)
            assert not await service.has_scope(contact_actor, output_id=output.id, output_version_id=output_version.id, scope="CONTACT")

            # A pending request cannot read either the exact document version
            # or discovery.  The checks use the production service paths.
            pending_discovery = await service.create(
                contact_actor,
                ResearchAccessRequestCreate(
                    research_output_id=output.id,
                    research_discovery_version_id=discovery_v1.id,
                    requester_project_id=project_id,
                    requested_scopes=["DISCOVERY_READ"],
                ),
            )
            assert pending_discovery.status == "PENDING"
            assert not await service.has_scope(contact_actor, discovery_version_id=discovery_v1.id, scope="DISCOVERY_READ")
            app.dependency_overrides[get_session] = override_session
            app.dependency_overrides[get_authenticated_principal] = lambda: contact_actor
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                pending_discovery_response = await client.get(f"/research/discoveries/{discovery.id}/versions/{discovery_v1.id}/access")
                assert pending_discovery_response.status_code == 404
            app.dependency_overrides.clear()
            with pytest.raises(HTTPException) as pending_access:
                await service.get(contact_actor, uuid.uuid4())
            assert pending_access.value.status_code == 404

            pending_document = await service.create(
                contact_actor,
                ResearchAccessRequestCreate(
                    research_output_id=output.id,
                    research_output_version_id=output_version.id,
                    requester_project_id=project_id,
                    requested_scopes=["FULL_DOCUMENT_READ"],
                ),
            )
            assert pending_document.status == "PENDING"
            with pytest.raises(HTTPException) as pending_document_error:
                await ResearchService(session).get_version(contact_actor, output.id, output_version.id)
            assert pending_document_error.value.status_code == 404
            assert not (await session.scalars(select(InvestorShareGrant).where(InvestorShareGrant.request_id.in_([pending_discovery.id, pending_document.id])))).all()

            # DISCOVERY_READ authorizes only the approved, exact version and
            # projects the safe public/matchable fields through the real route.
            discovery_request = await service.decide(principal(owner_id, owner_email), pending_discovery.id, "ACCEPTED", ResearchAccessDecision())
            assert discovery_request.granted_scopes == ["DISCOVERY_READ"]
            app.dependency_overrides[get_session] = override_session
            app.dependency_overrides[get_authenticated_principal] = lambda: contact_actor
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                discovery_response = await client.get(f"/research/discoveries/{discovery.id}/versions/{discovery_v1.id}/access")
                assert discovery_response.status_code == 200
                body = discovery_response.json()
                assert body["version_id"] == str(discovery_v1.id)
                assert body["fields"] == {"domains": ["public domain"], "research_problem": ["public problem"]}
                assert "evidence" not in body and "private_text" not in str(body)
                denied_v2 = await client.get(f"/research/discoveries/{discovery.id}/versions/{discovery_v2.id}/access")
                assert denied_v2.status_code == 404
            app.dependency_overrides.clear()
            discovery_audit = (await session.scalars(select(AuditLog).where(AuditLog.action == "RESEARCH_DISCOVERY_ACCESSED", AuditLog.resource_id == discovery_v1.id))).all()
            assert len(discovery_audit) == 1
            assert discovery_audit[0].metadata_json["scope"] == "DISCOVERY_READ"
            assert discovery_audit[0].metadata_json["grant_id"]
            assert "private_text" not in str(discovery_audit[0].metadata_json)
            await service.revoke(principal(owner_id, owner_email), pending_discovery.id)
            app.dependency_overrides[get_session] = override_session
            app.dependency_overrides[get_authenticated_principal] = lambda: contact_actor
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                assert (await client.get(f"/research/discoveries/{discovery.id}/versions/{discovery_v1.id}/access")).status_code == 404
            app.dependency_overrides.clear()
            assert len((await session.scalars(select(AuditLog).where(AuditLog.action == "RESEARCH_DISCOVERY_ACCESSED", AuditLog.resource_id == discovery_v1.id))).all()) == 1

            # Access decisions and revocation never mutate authoritative IP or
            # ownership metadata.
            rights_before = (list(output.authors), output.rights_holder, output.licence, output.visibility, output.publication_ready, profile.user_id)
            ip_request = await service.create(
                contact_actor,
                ResearchAccessRequestCreate(
                    research_output_id=output.id,
                    research_output_version_id=output_version.id,
                    requester_project_id=project_id,
                    requested_scopes=["FULL_DOCUMENT_READ", "COLLABORATION"],
                ),
            )
            await service.decide(principal(owner_id, owner_email), ip_request.id, "ACCEPTED", ResearchAccessDecision())
            await service.revoke(principal(owner_id, owner_email), ip_request.id)
            await session.refresh(output); await session.refresh(profile)
            assert rights_before == (list(output.authors), output.rights_holder, output.licence, output.visibility, output.publication_ready, profile.user_id)
    finally:
        app.dependency_overrides.clear()
        async with access_factory() as session:
            if project_id:
                await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
                await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id)); await session.execute(delete(Project).where(Project.id == project_id))
            await session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_([owner_id, requester_id])))
            await session.execute(delete(InvestorShareGrant).where(InvestorShareGrant.recipient_user_id == requester_id))
            await session.execute(delete(ResearchAccessRequest).where(ResearchAccessRequest.requester_user_id == requester_id))
            if discovery_id:
                await session.execute(delete(ResearchDiscoveryVersion).where(ResearchDiscoveryVersion.discovery_id == discovery_id))
                await session.execute(delete(ResearchDiscovery).where(ResearchDiscovery.id == discovery_id))
            await session.execute(delete(ResearchExtractionRun).where(ResearchExtractionRun.owner_user_id == owner_id))
            await session.execute(delete(ResearchOutputVersion).where(ResearchOutputVersion.uploaded_by_user_id == owner_id))
            await session.execute(delete(DocumentVersion).where(DocumentVersion.uploaded_by_user_id == owner_id)); await session.execute(delete(Document).where(Document.owner_user_id == owner_id))
            await session.execute(delete(ResearchOutput).where(ResearchOutput.researcher_profile_id.in_(select(ResearcherProfile.id).where(ResearcherProfile.user_id == owner_id))))
            await session.execute(delete(ResearcherProfile).where(ResearcherProfile.user_id == owner_id)); await session.execute(delete(User).where(User.id.in_([owner_id, requester_id]))); await session.commit()
