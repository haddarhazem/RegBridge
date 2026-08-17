import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.documents.schemas import Classification, DocumentResponse, DocumentUploadResponse, DocumentVersionResponse, DocumentVisibility, ProcessingJobCreate, ProcessingJobResponse
from app.modules.documents.service import DocumentService
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal

router = APIRouter(tags=["documents"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


def document_response(document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        owner_user_id=document.owner_user_id,
        project_id=document.project_id,
        title=document.title,
        document_type=document.document_type,
        classification=document.classification,
        visibility=document.visibility,
        processing_status=document.processing_status,
        current_version_id=document.current_version_id,
        deleted_at=document.deleted_at,
    )


def version_response(version) -> DocumentVersionResponse:
    return DocumentVersionResponse(
        id=version.id,
        document_id=version.document_id,
        version_number=version.version_number,
        original_filename=version.original_filename,
        mime_type=version.mime_type,
        size_bytes=version.size_bytes,
        sha256=version.sha256,
        malware_scan_status=version.malware_scan_status,
        created_at=version.created_at,
    )


@router.post("/projects/{project_id}/documents", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: uuid.UUID,
    principal: Principal,
    session: Session,
    upload: Annotated[UploadFile, File(...)],
    title: Annotated[str | None, Query(max_length=255)] = None,
    classification: Classification = "confidential",
    visibility: DocumentVisibility = "private",
) -> DocumentUploadResponse:
    document, version = await DocumentService(session).upload_first(principal, project_id, upload, title, classification, visibility)
    return DocumentUploadResponse(document=document_response(document), version=version_response(version))


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: uuid.UUID, principal: Principal, session: Session) -> DocumentResponse:
    document = await DocumentService(session).get_document(principal, document_id)
    return document_response(document)


@router.post("/documents/{document_id}/versions", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_version(document_id: uuid.UUID, principal: Principal, session: Session, upload: Annotated[UploadFile, File(...)]) -> DocumentUploadResponse:
    document, version = await DocumentService(session).upload_replacement(principal, document_id, upload)
    return DocumentUploadResponse(document=document_response(document), version=version_response(version))


@router.get("/documents/{document_id}/versions/{version_id}/download")
async def download_version(document_id: uuid.UUID, version_id: uuid.UUID, principal: Principal, session: Session) -> StreamingResponse:
    document, version, stream = await DocumentService(session).download(principal, document_id, version_id)
    filename = quote(version.original_filename.replace("\r", "").replace("\n", ""))
    return StreamingResponse(stream, media_type=version.mime_type, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"})


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, principal: Principal, session: Session) -> None:
    await DocumentService(session).soft_delete(principal, document_id)


@router.post("/documents/{document_id}/versions/{version_id}/processing-jobs", response_model=ProcessingJobResponse, status_code=status.HTTP_201_CREATED)
async def create_processing_job(document_id: uuid.UUID, version_id: uuid.UUID, data: ProcessingJobCreate, principal: Principal, session: Session) -> ProcessingJobResponse:
    job = await DocumentService(session).create_processing_job(principal, document_id, version_id, data)
    return ProcessingJobResponse(id=job.id, document_version_id=job.document_version_id, job_type=job.job_type, idempotency_key=job.idempotency_key, status=job.status)
