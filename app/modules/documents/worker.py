"""Small PostgreSQL-backed worker for immutable document-version extraction."""

from __future__ import annotations

import asyncio
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.observability import emit_event, elapsed_ms, metrics
from app.modules.documents.extraction import ExtractionError, ExtractionResult, extract_native, extraction_status
from app.modules.documents.models import Document, DocumentProcessingJob, DocumentVersion
from app.modules.documents.ocr import OcrProvider, get_ocr_provider
from app.modules.documents.storage import ObjectStorage, get_object_storage
from app.modules.documents.validation import validate_file


EXTRACTION_JOB_TYPE = "extract_text"
PENDING_STATES = {"queued"}


class DocumentExtractionWorker:
    """Claim and process one immutable version at a time."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: ObjectStorage | None = None,
        ocr_provider: OcrProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.storage = storage or get_object_storage()
        self.ocr_provider = ocr_provider
        self.settings = settings or get_settings()

    async def process_version(self, version_id: uuid.UUID) -> bool:
        claimed = await self._claim(version_id=version_id)
        if claimed is None:
            return False
        return await self._process_claimed(claimed)

    async def process_pending_once(self) -> bool:
        claimed = await self._claim()
        if claimed is None:
            return False
        return await self._process_claimed(claimed)

    async def retry_failed(self, version_id: uuid.UUID) -> bool:
        async with self.session.begin():
            job = await self.session.scalar(
                select(DocumentProcessingJob)
                .where(DocumentProcessingJob.document_version_id == version_id, DocumentProcessingJob.job_type == EXTRACTION_JOB_TYPE)
                .with_for_update()
            )
            if job is None:
                raise HTTPException(status_code=404, detail="Document processing job not found")
            if job.status != "failed":
                return False
            if job.attempt_count >= self.settings.document_extraction_max_attempts:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document processing retry limit reached")
            job.status = "queued"
            job.error_message = None
            job.started_at = None
            job.completed_at = None
            await self._set_version_state(version_id, "pending", failure_category=None)
        return True

    async def _claim(self, *, version_id: uuid.UUID | None = None) -> tuple[uuid.UUID, uuid.UUID] | None:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=self.settings.document_extraction_stale_after_seconds)
        async with self.session.begin():
            await self.session.execute(
                update(DocumentProcessingJob)
                .where(DocumentProcessingJob.job_type == EXTRACTION_JOB_TYPE, DocumentProcessingJob.status == "running", DocumentProcessingJob.started_at < stale_before)
                .values(status="queued", started_at=None, error_message="STALE_PROCESSING_RECOVERED")
            )
            query = select(DocumentProcessingJob).where(DocumentProcessingJob.job_type == EXTRACTION_JOB_TYPE, DocumentProcessingJob.status.in_(PENDING_STATES))
            if version_id is not None:
                query = query.where(DocumentProcessingJob.document_version_id == version_id)
            job = await self.session.scalar(query.order_by(DocumentProcessingJob.created_at, DocumentProcessingJob.id).with_for_update(skip_locked=True))
            if job is None:
                return None
            job.status = "running"
            job.attempt_count += 1
            job.started_at = now
            job.error_message = None
            await self._set_version_state(job.document_version_id, "processing", failure_category=None)
            return job.id, job.document_version_id

    async def _process_claimed(self, claimed: tuple[uuid.UUID, uuid.UUID]) -> bool:
        job_id, version_id = claimed
        started = time.perf_counter()
        try:
            version, document = await self._trusted_version(version_id)
            if version is None or document is None or document.deleted_at is not None:
                raise ExtractionError("STORAGE_READ_FAILED", "Document version is unavailable")
            if version.malware_scan_status != "clean":
                raise ExtractionError("UNSUPPORTED_FORMAT", "Document version did not pass the security gate")
            if extraction_status(version) == "ready" or version.extracted_text:
                await self._complete(job_id, version_id, None)
                return True

            payload = await self._read_source(version.storage_key)
            suffix = Path(version.original_filename).suffix.lower()
            with tempfile.NamedTemporaryFile(prefix="regbridge-extraction-", suffix=suffix, delete=False) as handle:
                source_path = Path(handle.name)
                handle.write(payload)
            try:
                try:
                    validated = validate_file(source_path, version.original_filename, version.mime_type)
                except (OSError, ValueError) as exc:
                    raise ExtractionError("NATIVE_EXTRACTION_FAILED", "Stored document failed validation") from exc
                try:
                    result = await asyncio.to_thread(extract_native, source_path, validated.extension, min_pdf_chars=self.settings.document_native_text_min_chars)
                except ExtractionError as exc:
                    if exc.category != "OCR_REQUIRED":
                        raise
                    if not self.settings.document_external_processing_enabled:
                        raise ExtractionError("EXTERNAL_PROCESSING_DISABLED", "External document processing is disabled") from exc
                    provider = self.ocr_provider or get_ocr_provider()
                    result = await provider.extract(payload, version.original_filename, validated.mime_type)
                if not result.normalized_text:
                    raise ExtractionError("EMPTY_EXTRACTION", "Document contains no usable text")
                await self._complete(job_id, version_id, result)
                metrics.increment("document_extraction_completed_total", component="document_extraction", method=result.method, status="ready")
                return True
            finally:
                source_path.unlink(missing_ok=True)
        except ExtractionError as exc:
            await self._fail(job_id, version_id, exc.category)
            metrics.increment("document_extraction_failed_total", component="document_extraction", error_category=exc.category, status="failed")
            return False
        except Exception as exc:
            await self._fail(job_id, version_id, "STORAGE_READ_FAILED")
            metrics.increment("document_extraction_failed_total", component="document_extraction", error_category="STORAGE_READ_FAILED", status="failed")
            emit_event("document.extraction.unexpected_failure", component="document_extraction", error_category=type(exc).__name__)
            return False
        finally:
            metrics.observe("document_extraction_duration_ms", elapsed_ms(started), component="document_extraction", status="completed")

    async def _trusted_version(self, version_id: uuid.UUID):
        async with self.session.begin():
            row = await self.session.execute(
                select(DocumentVersion, Document)
                .join(Document, Document.id == DocumentVersion.document_id)
                .where(DocumentVersion.id == version_id)
            )
            result = row.first()
        return result if result is not None else (None, None)

    async def _read_source(self, storage_key: str) -> bytes:
        chunks: list[bytes] = []
        total = 0
        async for chunk in self.storage.stream(storage_key):
            total += len(chunk)
            if total > self.settings.document_max_upload_bytes:
                raise ExtractionError("STORAGE_READ_FAILED", "Document exceeds the configured processing limit")
            chunks.append(chunk)
        if not chunks:
            raise ExtractionError("STORAGE_READ_FAILED", "Document source is empty")
        return b"".join(chunks)

    async def _complete(self, job_id: uuid.UUID, version_id: uuid.UUID, result: ExtractionResult | None) -> None:
        now = datetime.now(timezone.utc)
        async with self.session.begin():
            job = await self.session.scalar(select(DocumentProcessingJob).where(DocumentProcessingJob.id == job_id).with_for_update())
            version = await self.session.scalar(select(DocumentVersion).where(DocumentVersion.id == version_id).with_for_update())
            document = await self.session.scalar(select(Document).join(DocumentVersion, DocumentVersion.document_id == Document.id).where(DocumentVersion.id == version_id).with_for_update())
            if job is None or version is None:
                return
            if result is not None and extraction_status(version) != "ready" and not version.extracted_text:
                version.extracted_text = result.normalized_text
                existing = dict(version.extraction_metadata or {})
                existing["extraction"] = {
                    "status": "ready",
                    "method": result.method,
                    "extractor_version": result.extractor_version,
                    "provider": result.provider,
                    "model": result.model,
                    "page_count": len(result.pages),
                    "text_sha256": result.text_sha256,
                    "processed_at": now.isoformat(),
                }
                version.extraction_metadata = existing
            job.status = "succeeded"
            job.completed_at = now
            if document is not None and document.current_version_id == version_id:
                document.processing_status = "ready"
            emit_event("document.extraction.completed", component="document_extraction", document_version_id=version_id, method=result.method if result else "existing", status="ready", duration_ms=None)

    async def _fail(self, job_id: uuid.UUID, version_id: uuid.UUID, category: str) -> None:
        now = datetime.now(timezone.utc)
        async with self.session.begin():
            job = await self.session.scalar(select(DocumentProcessingJob).where(DocumentProcessingJob.id == job_id).with_for_update())
            if job is not None:
                job.status = "failed"
                job.completed_at = now
                job.error_message = category
            await self._set_version_state(version_id, "failed", failure_category=category, processed_at=now)

    async def _set_version_state(self, version_id: uuid.UUID, state: str, *, failure_category: str | None, processed_at: datetime | None = None) -> None:
        version = await self.session.scalar(select(DocumentVersion).where(DocumentVersion.id == version_id).with_for_update())
        if version is None:
            return
        metadata = dict(version.extraction_metadata or {})
        extraction = dict(metadata.get("extraction") or {})
        extraction.update({"status": state, "failure_category": failure_category})
        if processed_at is not None:
            extraction["processed_at"] = processed_at.isoformat()
        metadata["extraction"] = extraction
        version.extraction_metadata = metadata
        document = await self.session.scalar(select(Document).join(DocumentVersion, DocumentVersion.document_id == Document.id).where(DocumentVersion.id == version_id).with_for_update())
        if document is not None and document.current_version_id == version_id:
            # Extraction metadata has a pending state; the persisted document
            # state uses the V2.1-compatible queued value instead.
            document.processing_status = "queued" if state == "pending" else state


async def process_document_version(version_id: uuid.UUID) -> None:
    """FastAPI background-task entry point with an independent database session."""
    from app.db.session import get_session_factory

    async with get_session_factory()() as session:
        await DocumentExtractionWorker(session).process_version(version_id)


async def process_pending_batch(limit: int | None = None) -> int:
    """Process a bounded batch using independent sessions and row locking."""
    from app.db.session import get_session_factory

    concurrency = limit or get_settings().document_extraction_concurrency
    concurrency = max(1, min(concurrency, get_settings().document_extraction_concurrency))

    async def run_one() -> bool:
        async with get_session_factory()() as session:
            return await DocumentExtractionWorker(session).process_pending_once()

    results = await asyncio.gather(*(run_one() for _ in range(concurrency)))
    return sum(results)
