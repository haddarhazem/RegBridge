from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import AuditLog
from app.modules.documents.models import Document, DocumentVersion
from app.modules.documents.scanner import MalwareScanner, get_malware_scanner
from app.modules.documents.service import DocumentService, build_storage_key
from app.modules.documents.storage import ObjectStorage, get_object_storage
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.research.models import ResearchOutput, ResearchOutputVersion, ResearcherProfile
from app.modules.research.schemas import ResearchOutputCreate, ResearcherProfileUpsert


def missing_rights_fields(rights_holder: str | None, licence: str | None) -> list[str]:
    return [field for field, value in (("rights_holder", rights_holder), ("licence", licence)) if not value or not value.strip()]


class ResearchService:
    def __init__(self, session: AsyncSession, storage: ObjectStorage | None = None, scanner: MalwareScanner | None = None, max_upload_bytes: int | None = None) -> None:
        self.session = session
        self.documents = DocumentService(session, storage=storage or get_object_storage(), scanner=scanner or get_malware_scanner(), max_upload_bytes=max_upload_bytes)

    async def get_profile(self, actor: AuthenticatedPrincipal) -> ResearcherProfile:
        profile = await self.session.scalar(select(ResearcherProfile).where(ResearcherProfile.user_id == actor.user_id))
        if profile is None:
            raise HTTPException(status_code=404, detail="Researcher profile not found")
        return profile

    async def upsert_profile(self, actor: AuthenticatedPrincipal, data: ResearcherProfileUpsert) -> ResearcherProfile:
        async with self.session.begin():
            profile = await self.session.scalar(select(ResearcherProfile).where(ResearcherProfile.user_id == actor.user_id).with_for_update())
            created = profile is None
            if profile is None:
                profile = ResearcherProfile(user_id=actor.user_id, affiliation=data.affiliation, scientific_domains=data.scientific_domains)
                self.session.add(profile)
                await self.session.flush()
            else:
                profile.affiliation = data.affiliation
                profile.scientific_domains = data.scientific_domains
            self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="researcher_profile.created" if created else "researcher_profile.updated", resource_type="researcher_profile", resource_id=profile.id, metadata_json={"profile_id": str(profile.id)}))
        return profile

    async def create_output(self, actor: AuthenticatedPrincipal, data: ResearchOutputCreate) -> ResearchOutput:
        profile = await self.get_profile(actor)
        profile_id = profile.id
        missing = missing_rights_fields(data.rights_holder, data.licence)
        await self.session.rollback()
        async with self.session.begin():
            output = ResearchOutput(researcher_profile_id=profile_id, title=data.title.strip(), authors=data.authors, rights_holder=data.rights_holder, licence=data.licence, visibility=data.visibility, rights_metadata_status="COMPLETE" if not missing else "INCOMPLETE", publication_ready=not missing)
            self.session.add(output)
            await self.session.flush()
            self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="research_output.created", resource_type="research_output", resource_id=output.id, metadata_json={"research_output_id": str(output.id), "visibility": output.visibility, "rights_metadata_status": output.rights_metadata_status}))
        return output

    async def _owned_output(self, actor: AuthenticatedPrincipal, output_id: uuid.UUID, *, lock: bool = False) -> ResearchOutput:
        query = select(ResearchOutput).join(ResearcherProfile, ResearcherProfile.id == ResearchOutput.researcher_profile_id).where(ResearchOutput.id == output_id, ResearcherProfile.user_id == actor.user_id)
        if lock:
            query = query.with_for_update()
        output = await self.session.scalar(query)
        if output is None:
            raise HTTPException(status_code=404, detail="Research output not found")
        return output

    async def list_outputs(self, actor: AuthenticatedPrincipal) -> list[ResearchOutput]:
        await self.get_profile(actor)
        return list((await self.session.scalars(select(ResearchOutput).join(ResearcherProfile).where(ResearcherProfile.user_id == actor.user_id).order_by(ResearchOutput.created_at, ResearchOutput.id))).all())

    async def get_output(self, actor: AuthenticatedPrincipal, output_id: uuid.UUID) -> ResearchOutput:
        return await self._owned_output(actor, output_id)

    async def upload_version(self, actor: AuthenticatedPrincipal, output_id: uuid.UUID, upload: UploadFile) -> tuple[ResearchOutput, ResearchOutputVersion, DocumentVersion]:
        await self.session.rollback()
        path: Path | None = None
        storage_key = ""
        stored = False
        try:
            async with self.session.begin():
                output = await self._owned_output(actor, output_id, lock=True)
                path, size, checksum = await self.documents._stage(upload)
                if size == 0:
                    raise HTTPException(status_code=422, detail="Research document must not be empty")
                validated = self.documents._validate(path, upload)
                document_id = uuid.uuid4()
                document_version_id = uuid.uuid4()
                research_version_id = uuid.uuid4()
                storage_key = build_storage_key(document_id, document_version_id)
                scan = await self.documents._store_and_scan(path, storage_key, validated)
                stored = True
                if scan.status != "clean":
                    raise HTTPException(status_code=422, detail="Research document did not pass the configured safety scan")
                last = await self.session.scalar(select(ResearchOutputVersion.version_number).where(ResearchOutputVersion.research_output_id == output.id).order_by(ResearchOutputVersion.version_number.desc()).limit(1)) or 0
                document = Document(id=document_id, owner_user_id=actor.user_id, project_id=None, title=output.title, document_type=validated.extension.removeprefix("."), classification="confidential", visibility="private", processing_status="uploaded", current_version_id=document_version_id)
                document_version = DocumentVersion(id=document_version_id, document_id=document.id, version_number=1, original_filename=upload.filename or "document", storage_key=storage_key, mime_type=validated.mime_type, size_bytes=size, sha256=checksum, malware_scan_status="clean", uploaded_by_user_id=actor.user_id)
                research_version = ResearchOutputVersion(id=research_version_id, research_output_id=output.id, document_version_id=document_version.id, version_number=int(last) + 1, uploaded_by_user_id=actor.user_id, content_hash=checksum)
                self.session.add_all([document, document_version, research_version])
                self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="research_output.version_uploaded", resource_type="research_output_version", resource_id=research_version.id, metadata_json={"research_output_id": str(output.id), "version_id": str(research_version.id), "document_version_id": str(document_version.id), "version_number": research_version.version_number, "sha256": checksum}))
                await self.session.flush()
            return output, research_version, document_version
        except Exception:
            if stored:
                await self.documents.storage.delete(storage_key)
            raise
        finally:
            if path is not None:
                path.unlink(missing_ok=True)

    async def list_versions(self, actor: AuthenticatedPrincipal, output_id: uuid.UUID) -> list[tuple[ResearchOutputVersion, DocumentVersion]]:
        output = await self._owned_output(actor, output_id)
        rows = await self.session.execute(select(ResearchOutputVersion, DocumentVersion).join(DocumentVersion, DocumentVersion.id == ResearchOutputVersion.document_version_id).where(ResearchOutputVersion.research_output_id == output.id).order_by(ResearchOutputVersion.version_number))
        return list(rows.all())

    async def current_version(self, actor: AuthenticatedPrincipal, output_id: uuid.UUID) -> tuple[ResearchOutputVersion, DocumentVersion]:
        await self._owned_output(actor, output_id)
        row = await self.session.execute(select(ResearchOutputVersion, DocumentVersion).join(DocumentVersion, DocumentVersion.id == ResearchOutputVersion.document_version_id).where(ResearchOutputVersion.research_output_id == output_id).order_by(ResearchOutputVersion.version_number.desc()).limit(1))
        result = row.first()
        if result is None:
            raise HTTPException(status_code=404, detail="Research output version not found")
        return result

    async def get_version(self, actor: AuthenticatedPrincipal, output_id: uuid.UUID, version_id: uuid.UUID) -> tuple[ResearchOutputVersion, DocumentVersion]:
        await self._owned_output(actor, output_id)
        row = await self.session.execute(select(ResearchOutputVersion, DocumentVersion).join(DocumentVersion, DocumentVersion.id == ResearchOutputVersion.document_version_id).where(ResearchOutputVersion.research_output_id == output_id, ResearchOutputVersion.id == version_id))
        result = row.first()
        if result is None:
            raise HTTPException(status_code=404, detail="Research output version not found")
        return result

    async def download(self, actor: AuthenticatedPrincipal, output_id: uuid.UUID, version_id: uuid.UUID) -> tuple[DocumentVersion, AsyncIterator[bytes]]:
        _, version = await self.get_version(actor, output_id, version_id)
        document, selected, stream = await self.documents.download(actor, version.document_id, version.id)
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="research_output.version_accessed", resource_type="research_output_version", resource_id=version_id, metadata_json={"research_output_id": str(output_id), "document_version_id": str(selected.id)}))
        await self.session.commit()
        return selected, stream
