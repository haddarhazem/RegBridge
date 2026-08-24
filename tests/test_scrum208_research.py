import asyncio
import hashlib
import io
import uuid
import zipfile

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from starlette.datastructures import UploadFile

from app.main import app
from app.db.session import get_session
from app.modules.audit import AuditLog
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.models import User
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.research.models import ResearchOutput, ResearchOutputVersion, ResearcherProfile
from app.modules.research.schemas import ResearchOutputCreate, ResearcherProfileUpsert
from app.modules.research.service import ResearchService

from test_scrum203_matching import actor, make_user
from test_scrum205_verification import verification_factory


class MemoryStorage:
    def __init__(self):
        self.items: dict[str, bytes] = {}

    async def put_file(self, path, key, content_type):
        self.items[key] = path.read_bytes()

    def stream(self, key):
        value = self.items[key]

        async def iterator():
            yield value

        return iterator()

    async def delete(self, key):
        self.items.pop(key, None)


class CleanScanner:
    async def scan(self, path):
        from app.modules.documents.scanner import ScanResult

        return ScanResult("clean")


def upload(data: bytes, filename: str = "paper.pdf", content_type: str = "application/pdf") -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename, headers={"content-type": content_type})


def docx_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return output.getvalue()


async def cleanup_research(factory, principals):
    user_ids = [item.user_id for item in principals]
    async with factory() as session:
        profile_ids = list((await session.scalars(select(ResearcherProfile.id).where(ResearcherProfile.user_id.in_(user_ids)))).all())
        output_ids = list((await session.scalars(select(ResearchOutput.id).where(ResearchOutput.researcher_profile_id.in_(profile_ids)))).all())
        research_version_ids = list((await session.scalars(select(ResearchOutputVersion.id).where(ResearchOutputVersion.research_output_id.in_(output_ids)))).all())
        document_version_ids = list((await session.scalars(select(ResearchOutputVersion.document_version_id).where(ResearchOutputVersion.id.in_(research_version_ids)))).all())
        document_ids = list((await session.scalars(select(DocumentVersion.document_id).where(DocumentVersion.id.in_(document_version_ids)))).all())
        await session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(user_ids)))
        await session.execute(delete(ResearchOutputVersion).where(ResearchOutputVersion.id.in_(research_version_ids)))
        await session.execute(delete(DocumentVersion).where(DocumentVersion.id.in_(document_version_ids)))
        await session.execute(delete(Document).where(Document.id.in_(document_ids)))
        await session.execute(delete(ResearchOutput).where(ResearchOutput.id.in_(output_ids)))
        await session.execute(delete(ResearcherProfile).where(ResearcherProfile.id.in_(profile_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_scrum208_private_versioned_research_lifecycle(verification_factory):
    researcher = await make_user(verification_factory, "scrum208-researcher")
    outsider = await make_user(verification_factory, "scrum208-outsider")
    storage = MemoryStorage()
    try:
        async with verification_factory() as session:
            service = ResearchService(session, storage=storage, scanner=CleanScanner(), max_upload_bytes=100000)
            profile = await service.upsert_profile(researcher, ResearcherProfileUpsert(affiliation="Research Lab", scientific_domains=["privacy", "systems"]))
            assert profile.user_id == researcher.user_id
            with pytest.raises(HTTPException) as missing_profile:
                await service.get_profile(outsider)
            assert missing_profile.value.status_code == 404

            incomplete = await service.create_output(researcher, ResearchOutputCreate(title="Controlled Research Example", authors=["Researcher A", "Researcher B"]))
            assert incomplete.visibility == "private"
            assert incomplete.rights_metadata_status == "INCOMPLETE" and incomplete.publication_ready is False
            incomplete_id = incomplete.id
            complete = await service.create_output(researcher, ResearchOutputCreate(title="Rights Complete", authors=["Researcher A"], rights_holder="Research Institute", licence="CC BY 4.0"))
            assert complete.rights_metadata_status == "COMPLETE" and complete.publication_ready is True and complete.visibility == "private"
            complete_id = complete.id

            first_bytes = b"%PDF-1.7\ncontrolled research v1"
            _, v1, d1 = await service.upload_version(researcher, incomplete_id, upload(first_bytes, "../paper-v1.pdf"))
            second_bytes = b"%PDF-1.7\ncontrolled research v2"
            _, v2, d2 = await service.upload_version(researcher, incomplete_id, upload(second_bytes, "paper-v2.pdf"))
            assert v1.version_number == 1 and v2.version_number == 2 and v1.id != v2.id
            assert v1.content_hash == hashlib.sha256(first_bytes).hexdigest()
            assert v2.content_hash == hashlib.sha256(second_bytes).hexdigest()
            v1_hash = v1.content_hash
            assert d1.original_filename == "../paper-v1.pdf" and ".." not in d1.storage_key
            v1_id = v1.id

            versions = await service.list_versions(researcher, incomplete_id)
            assert [item[0].version_number for item in versions] == [1, 2]
            old_version, old_document = await service.get_version(researcher, incomplete_id, v1.id)
            assert old_version.content_hash == v1.content_hash and old_document.sha256 == v1.content_hash
            selected, stream = await service.download(researcher, incomplete_id, v1.id)
            assert b"".join([chunk async for chunk in stream]) == first_bytes
            with pytest.raises(HTTPException) as denied:
                await service.download(outsider, incomplete_id, v1.id)
            assert denied.value.status_code == 404

            with pytest.raises(HTTPException) as empty:
                await service.upload_version(researcher, incomplete_id, upload(b"", "empty.pdf"))
            assert empty.value.status_code == 422
            with pytest.raises(HTTPException) as unsupported:
                await service.upload_version(researcher, incomplete_id, upload(b"MZ", "program.exe", "application/octet-stream"))
            assert unsupported.value.status_code == 415

            docx_version = await service.upload_version(researcher, complete_id, upload(docx_bytes(), "paper.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
            txt_bytes = "UTF-8 recherche éthique".encode("utf-8")
            txt_version = await service.upload_version(researcher, complete_id, upload(txt_bytes, "paper.txt", "text/plain"))
            assert docx_version[2].mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            assert txt_version[2].mime_type == "text/plain"
            _, txt_stream = await service.download(researcher, complete_id, txt_version[1].id)
            assert b"".join([chunk async for chunk in txt_stream]) == txt_bytes

            duplicate = await service.upload_version(researcher, incomplete_id, upload(first_bytes, "same-bytes.pdf"))
            assert duplicate[1].version_number == 3 and duplicate[1].id != v1_id and duplicate[2].sha256 == v1_hash

            other_output = await service.create_output(researcher, ResearchOutputCreate(title="Separate Output", authors=["Researcher A"]))
            with pytest.raises(HTTPException) as wrong_output:
                await service.get_version(researcher, other_output.id, v1_id)
            assert wrong_output.value.status_code == 404

        async def concurrent_upload(data: bytes):
            async with verification_factory() as concurrent_session:
                return await ResearchService(concurrent_session, storage=storage, scanner=CleanScanner(), max_upload_bytes=100000).upload_version(researcher, incomplete_id, upload(data, "concurrent.pdf"))

        concurrent = await asyncio.gather(concurrent_upload(b"%PDF-1.7\nconcurrent-a"), concurrent_upload(b"%PDF-1.7\nconcurrent-b"))
        assert sorted(item[1].version_number for item in concurrent) == [4, 5]

        async with verification_factory() as fresh_session:
            fresh_versions = await ResearchService(fresh_session, storage=storage, scanner=CleanScanner(), max_upload_bytes=100000).list_versions(researcher, incomplete_id)
            assert [item[0].version_number for item in fresh_versions] == [1, 2, 3, 4, 5]
            assert [item[0].content_hash for item in fresh_versions[:2]] == [hashlib.sha256(first_bytes).hexdigest(), hashlib.sha256(second_bytes).hexdigest()]
            current_version, _ = await ResearchService(fresh_session, storage=storage, scanner=CleanScanner(), max_upload_bytes=100000).current_version(researcher, incomplete_id)
            assert current_version.version_number == 5

        async def override_session():
            async with verification_factory() as route_session:
                yield route_session

        import app.modules.research.service as research_service_module

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_authenticated_principal] = lambda: researcher
        original_storage_factory = research_service_module.get_object_storage
        research_service_module.get_object_storage = lambda: storage
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                owner_download = await client.get(f"/research/outputs/{incomplete_id}/versions/{v1_id}/download")
                assert owner_download.status_code == 200 and hashlib.sha256(owner_download.content).hexdigest() == hashlib.sha256(first_bytes).hexdigest()
                app.dependency_overrides[get_authenticated_principal] = lambda: outsider
                outsider_download = await client.get(f"/research/outputs/{incomplete_id}/versions/{v1_id}/download")
                assert outsider_download.status_code == 404
                app.dependency_overrides.pop(get_authenticated_principal)
                unauthenticated = await client.get(f"/research/outputs/{incomplete_id}/versions/{v1_id}/download")
                assert unauthenticated.status_code == 401
        finally:
            research_service_module.get_object_storage = original_storage_factory
            app.dependency_overrides.clear()
    finally:
        await cleanup_research(verification_factory, [researcher, outsider])
