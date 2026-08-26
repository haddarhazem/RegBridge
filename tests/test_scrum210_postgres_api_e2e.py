import uuid

import httpx
import pytest
from sqlalchemy import delete, select

from app.main import app
from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.models import User
from app.modules.audit import AuditLog
from app.modules.research.discovery import DiscoveryService
from app.modules.research.models import (ResearchDiscovery, ResearchDiscoveryVersion, ResearchEvidenceRef,
    ResearchExtractionItem, ResearchExtractionRun, ResearchOutput, ResearchOutputVersion, ResearcherProfile)
from app.modules.documents.models import Document, DocumentVersion
from app.modules.research.schemas import ResearchDiscoveryCorrection
from test_scrum203_matching import make_user
from test_scrum205_verification import verification_factory


@pytest.mark.asyncio
async def test_scrum210_postgres_api_lifecycle_and_idor(verification_factory):
    owner = await make_user(verification_factory, "scrum210-owner")
    outsider = await make_user(verification_factory, "scrum210-outsider")
    output_id = uuid.uuid4(); research_version_id = uuid.uuid4(); document_id = uuid.uuid4(); document_version_id = uuid.uuid4(); run_id = uuid.uuid4()
    try:
        async with verification_factory() as session:
            profile = ResearcherProfile(id=uuid.uuid4(), user_id=owner.user_id, affiliation="Lab", scientific_domains=[])
            output = ResearchOutput(id=output_id, researcher_profile_id=profile.id, title="Controlled", authors=["A"], rights_holder="Institute", licence="CC BY", rights_metadata_status="COMPLETE", publication_ready=True)
            document = Document(id=document_id, owner_user_id=owner.user_id, project_id=None, title="Controlled", document_type="txt", classification="confidential", visibility="private", processing_status="uploaded", current_version_id=document_version_id)
            document_version = DocumentVersion(id=document_version_id, document_id=document_id, version_number=1, original_filename="paper.txt", storage_key=f"private/scrum210-{document_id}", mime_type="text/plain", size_bytes=15, sha256="a" * 64, malware_scan_status="clean", uploaded_by_user_id=owner.user_id)
            research_version = ResearchOutputVersion(id=research_version_id, research_output_id=output_id, document_version_id=document_version_id, version_number=1, uploaded_by_user_id=owner.user_id, content_hash="a" * 64)
            run = ResearchExtractionRun(id=run_id, owner_user_id=owner.user_id, research_output_id=output_id, research_output_version_id=research_version_id, document_version_id=document_version_id, source_sha256="a" * 64, strategy="extractive_evidence_locked", strategy_version="v1", provider="stub", model="stub", prompt_version="test", schema_version="v1", segmenter_version="v1", status="GENERATED", regbridge_abstract="")
            item = ResearchExtractionItem(id=uuid.uuid4(), run_id=run_id, field="domains", status="SUPPORTED", source_text="Explicit domain", item_order=0)
            ref = ResearchEvidenceRef(id=uuid.uuid4(), item_id=item.id, research_output_version_id=research_version_id, document_version_id=document_version_id, segment_id="SRC-001", locator={"document_version_id": str(document_version_id), "locator_type": "paragraph", "paragraph": 0, "start_char": 0, "end_char": 15}, item_order=0)
            session.add(profile); await session.flush()
            session.add(output); await session.flush()
            session.add_all([document, document_version, research_version]); await session.flush()
            session.add(run); await session.flush()
            session.add(item); await session.flush()
            session.add(ref); await session.commit()
            version = await DiscoveryService(session).initialize(owner, run_id)
            assert version.version_number == 1 and version.status == "DRAFT" and version.visibility["domains"] == "PRIVATE"
            discovery_id = version.discovery_id; v1_snapshot = version.content.copy()
            correction = await DiscoveryService(session).correct(owner, discovery_id, version.id, {"fields": {"domains": ["Explicit domain"]}}, {"domains": "PUBLIC", "abstract": "PUBLIC"})
            assert correction.version_number == 2 and correction.status == "DRAFT"
            await DiscoveryService(session).approve(owner, discovery_id, correction.id)
        async with verification_factory() as fresh:
            history = list((await fresh.scalars(select(ResearchDiscoveryVersion).where(ResearchDiscoveryVersion.discovery_id == discovery_id).order_by(ResearchDiscoveryVersion.version_number))).all())
            assert [v.version_number for v in history] == [1, 2] and history[0].content == v1_snapshot and history[1].status == "APPROVED"
        async def session_override():
            async with verification_factory() as session:
                yield session
        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_authenticated_principal] = lambda: owner
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            public = await client.get(f"/public/research/discoveries/{discovery_id}")
            assert public.status_code == 200 and public.json()["fields"] == {"domains": ["Explicit domain"]}
            app.dependency_overrides[get_authenticated_principal] = lambda: outsider
            denied = await client.get(f"/research/discoveries/{discovery_id}/current")
            assert denied.status_code == 404
            app.dependency_overrides.pop(get_authenticated_principal)
            unauthenticated = await client.get(f"/research/discoveries/{discovery_id}/current")
            assert unauthenticated.status_code == 401
    finally:
        app.dependency_overrides.clear()
        async with verification_factory() as session:
            await session.execute(delete(ResearchDiscoveryVersion).where(ResearchDiscoveryVersion.discovery_id.in_(select(ResearchDiscovery.id).where(ResearchDiscovery.research_output_id == output_id))))
            await session.execute(delete(ResearchDiscovery).where(ResearchDiscovery.research_output_id == output_id))
            await session.execute(delete(ResearchEvidenceRef).where(ResearchEvidenceRef.research_output_version_id == research_version_id))
            await session.execute(delete(ResearchExtractionItem).where(ResearchExtractionItem.run_id == run_id))
            await session.execute(delete(ResearchExtractionRun).where(ResearchExtractionRun.id == run_id))
            await session.execute(delete(ResearchOutputVersion).where(ResearchOutputVersion.id == research_version_id))
            await session.execute(delete(DocumentVersion).where(DocumentVersion.id == document_version_id)); await session.execute(delete(Document).where(Document.id == document_id))
            await session.execute(delete(ResearchOutput).where(ResearchOutput.id == output_id)); await session.execute(delete(ResearcherProfile).where(ResearcherProfile.user_id == owner.user_id)); await session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_([owner.user_id, outsider.user_id]))); await session.execute(delete(User).where(User.id.in_([owner.user_id, outsider.user_id]))); await session.commit()
