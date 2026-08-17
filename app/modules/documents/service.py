import hashlib
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import AuditLog
from app.modules.documents.authorization import DocumentAuthorizationPolicy
from app.modules.documents.models import Document, DocumentProcessingJob, DocumentVersion
from app.modules.documents.scanner import MalwareScanner, ScanResult, get_malware_scanner
from app.modules.documents.schemas import ProcessingJobCreate
from app.modules.documents.storage import ObjectStorage, get_object_storage
from app.modules.documents.validation import ValidatedFile, validate_file
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember


def build_storage_key(document_id: uuid.UUID, version_id: uuid.UUID) -> str:
    return f"documents/{document_id}/{version_id}"


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorage | None = None,
        scanner: MalwareScanner | None = None,
        policy: DocumentAuthorizationPolicy | None = None,
        max_upload_bytes: int | None = None,
    ) -> None:
        from app.core.config import get_settings

        self.session = session
        self.storage = storage or get_object_storage()
        self.scanner = scanner or get_malware_scanner()
        self.policy = policy or DocumentAuthorizationPolicy()
        self.max_upload_bytes = max_upload_bytes or get_settings().document_max_upload_bytes

    async def _stage(self, upload: UploadFile) -> tuple[Path, int, str]:
        if not upload.filename:
            raise HTTPException(status_code=422, detail="A filename is required")
        digest = hashlib.sha256()
        total = 0
        handle = tempfile.NamedTemporaryFile(prefix="regbridge-upload-", suffix=".tmp", delete=False)
        path = Path(handle.name)
        try:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > self.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="Document exceeds the configured size limit")
                digest.update(chunk)
                handle.write(chunk)
            handle.close()
            return path, total, digest.hexdigest()
        except BaseException:
            handle.close()
            path.unlink(missing_ok=True)
            raise

    async def _membership(self, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
        return await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id, ProjectMember.status == "active"))

    async def _authorize_upload(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> Project:
        project = await self.session.scalar(select(Project).where(Project.id == project_id))
        membership = await self._membership(project_id, actor.user_id) if project is not None else None
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if not self.policy.can_upload(membership):
            raise HTTPException(status_code=403, detail="Document upload is not permitted")
        return project

    async def _audit(self, actor: AuthenticatedPrincipal, action: str, document_id: uuid.UUID, metadata: dict, project_id: uuid.UUID | None = None) -> None:
        self.session.add(
            AuditLog(
                actor_user_id=actor.user_id,
                actor_type="user",
                action=action,
                resource_type="document",
                resource_id=document_id,
                project_id=project_id,
                metadata_json=metadata,
            )
        )

    async def _scan(self, path: Path) -> ScanResult:
        try:
            result = await self.scanner.scan(path)
            if result.status not in {"clean", "infected", "error"}:
                return ScanResult("error", "Unknown scanner result")
            return result
        except Exception as exc:
            return ScanResult("error", type(exc).__name__)

    async def _store_and_scan(self, path: Path, key: str, validated: ValidatedFile) -> ScanResult:
        try:
            await self.storage.put_file(path, key, validated.mime_type)
        except Exception:
            raise HTTPException(status_code=503, detail="Document storage is unavailable") from None
        return await self._scan(path)

    def _validate(self, path: Path, upload: UploadFile) -> ValidatedFile:
        try:
            return validate_file(path, upload.filename or "", upload.content_type)
        except ValueError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from None

    async def upload_first(
        self,
        actor: AuthenticatedPrincipal,
        project_id: uuid.UUID,
        upload: UploadFile,
        title: str | None,
        classification: str,
        visibility: str,
    ) -> tuple[Document, DocumentVersion]:
        await self._authorize_upload(actor, project_id)
        await self.session.rollback()
        path, size, checksum = await self._stage(upload)
        storage_key = ""
        stored = False
        try:
            validated = self._validate(path, upload)
            document_id = uuid.uuid4()
            version_id = uuid.uuid4()
            storage_key = build_storage_key(document_id, version_id)
            scan = await self._store_and_scan(path, storage_key, validated)
            stored = True
            safe = scan.status == "clean"
            async with self.session.begin():
                document = Document(
                    id=document_id,
                    owner_user_id=actor.user_id,
                    project_id=project_id,
                    title=title or upload.filename or "Document",
                    document_type=validated.extension.removeprefix("."),
                    classification=classification,
                    visibility=visibility,
                    processing_status="uploaded" if safe else "quarantined",
                )
                version = DocumentVersion(
                    id=version_id,
                    document_id=document_id,
                    version_number=1,
                    original_filename=upload.filename or "document",
                    storage_key=storage_key,
                    mime_type=validated.mime_type,
                    size_bytes=size,
                    sha256=checksum,
                    malware_scan_status=scan.status,
                    extraction_metadata={"scanner_detail": scan.detail} if scan.detail else {},
                    uploaded_by_user_id=actor.user_id,
                )
                self.session.add_all([document, version])
                if safe:
                    document.current_version_id = version_id
                await self._audit(actor, "document.created" if safe else "document.quarantined", document_id, {"version_id": str(version_id), "sha256": checksum}, project_id)
            return document, version
        except HTTPException:
            if stored:
                await self.storage.delete(storage_key)
            raise
        except Exception:
            if stored:
                await self.storage.delete(storage_key)
            raise
        finally:
            path.unlink(missing_ok=True)

    async def upload_replacement(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID, upload: UploadFile) -> tuple[Document, DocumentVersion]:
        document = await self.session.scalar(select(Document).where(Document.id == document_id, Document.deleted_at.is_(None)))
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if document.project_id is None:
            if document.owner_user_id != actor.user_id:
                raise HTTPException(status_code=403, detail="Document access denied")
        else:
            await self._authorize_upload(actor, document.project_id)
        await self.session.rollback()
        path, size, checksum = await self._stage(upload)
        storage_key = ""
        stored = False
        try:
            validated = self._validate(path, upload)
            version_id = uuid.uuid4()
            storage_key = build_storage_key(document.id, version_id)
            scan = await self._store_and_scan(path, storage_key, validated)
            stored = True
            async with self.session.begin():
                max_version = await self.session.scalar(select(func.max(DocumentVersion.version_number)).where(DocumentVersion.document_id == document.id)) or 0
                version = DocumentVersion(
                    id=version_id,
                    document_id=document.id,
                    version_number=max_version + 1,
                    original_filename=upload.filename or "document",
                    storage_key=storage_key,
                    mime_type=validated.mime_type,
                    size_bytes=size,
                    sha256=checksum,
                    malware_scan_status=scan.status,
                    extraction_metadata={"scanner_detail": scan.detail} if scan.detail else {},
                    uploaded_by_user_id=actor.user_id,
                )
                self.session.add(version)
                if scan.status == "clean":
                    document.current_version_id = version_id
                    document.processing_status = "uploaded"
                await self._audit(actor, "document.version.created" if scan.status == "clean" else "document.quarantined", document.id, {"version_id": str(version_id), "sha256": checksum}, document.project_id)
            return document, version
        except Exception:
            if stored:
                await self.storage.delete(storage_key)
            raise
        finally:
            path.unlink(missing_ok=True)

    async def _document_for_actor(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID) -> tuple[Document, ProjectMember | None]:
        document = await self.session.scalar(select(Document).where(Document.id == document_id, Document.deleted_at.is_(None)))
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        membership = await self._membership(document.project_id, actor.user_id) if document.project_id else None
        if not self.policy.can_read(document.visibility, document.classification, membership, document.owner_user_id, actor.user_id):
            raise HTTPException(status_code=404, detail="Document not found")
        return document, membership

    async def get_document(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID) -> Document:
        document, _ = await self._document_for_actor(actor, document_id)
        return document

    async def download(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID, version_id: uuid.UUID | None = None) -> tuple[Document, DocumentVersion, AsyncIterator[bytes]]:
        document, _ = await self._document_for_actor(actor, document_id)
        selected_id = version_id or document.current_version_id
        if selected_id is None:
            raise HTTPException(status_code=404, detail="Document version not found")
        version = await self.session.scalar(select(DocumentVersion).where(DocumentVersion.id == selected_id, DocumentVersion.document_id == document.id))
        if version is None or version.malware_scan_status != "clean":
            raise HTTPException(status_code=403, detail="Document version is not available")
        return document, version, self.storage.stream(version.storage_key)

    async def soft_delete(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID) -> None:
        document, membership = await self._document_for_actor(actor, document_id)
        if not self.policy.can_manage(membership, document.owner_user_id, actor.user_id):
            raise HTTPException(status_code=403, detail="Document deletion is not permitted")
        await self.session.rollback()
        async with self.session.begin():
            document.deleted_at = datetime.now(timezone.utc)
            await self._audit(actor, "document.deleted", document.id, {}, document.project_id)

    async def create_processing_job(self, actor: AuthenticatedPrincipal, document_id: uuid.UUID, version_id: uuid.UUID, data: ProcessingJobCreate) -> DocumentProcessingJob:
        document, _ = await self._document_for_actor(actor, document_id)
        version = await self.session.scalar(select(DocumentVersion).where(DocumentVersion.id == version_id, DocumentVersion.document_id == document.id))
        if version is None or version.malware_scan_status != "clean":
            raise HTTPException(status_code=403, detail="Document version is not usable")
        await self.session.rollback()
        async with self.session.begin():
            existing = await self.session.scalar(select(DocumentProcessingJob).where(DocumentProcessingJob.idempotency_key == data.idempotency_key))
            if existing is not None:
                return existing
            job = DocumentProcessingJob(id=uuid.uuid4(), document_version_id=version.id, job_type=data.job_type, idempotency_key=data.idempotency_key, status="queued")
            self.session.add(job)
            await self._audit(actor, "document.processing_job.created", document.id, {"version_id": str(version.id), "job_type": data.job_type}, document.project_id)
        return job
