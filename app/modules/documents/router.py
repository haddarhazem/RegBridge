import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.documents.schemas import Classification, DocumentResponse, DocumentUploadResponse, DocumentVersionResponse, DocumentVisibility, ProcessingJobCreate, ProcessingJobResponse
from app.modules.documents.contract_analysis_schemas import ContractAnalysisResponse, ContractClauseResponse, ContractEvidenceResponse, ContractPartyResponse
from app.modules.documents.contract_analysis_service import ContractAnalysisService
from app.modules.documents.contract_risk import calculate_contract_risk_index
from app.modules.documents.models import DocumentProcessingJob
from app.modules.documents.service import DocumentService
from app.modules.documents.extraction import extraction_status
from app.modules.documents.worker import process_document_version
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
    metadata = version.extraction_metadata if isinstance(version.extraction_metadata, dict) else {}
    extraction = metadata.get("extraction", {}) if isinstance(metadata.get("extraction", {}), dict) else {}
    return DocumentVersionResponse(
        id=version.id,
        document_id=version.document_id,
        version_number=version.version_number,
        original_filename=version.original_filename,
        mime_type=version.mime_type,
        size_bytes=version.size_bytes,
        sha256=version.sha256,
        malware_scan_status=version.malware_scan_status,
        extraction_status=extraction_status(version),
        extraction_method=extraction.get("method"),
        extraction_error=extraction.get("failure_category"),
        extracted_at=extraction.get("processed_at"),
        created_at=version.created_at,
    )


def analysis_response(analysis) -> ContractAnalysisResponse:
    metadata = analysis.missing_context[0] if isinstance(analysis.missing_context, list) and analysis.missing_context and isinstance(analysis.missing_context[0], dict) else {}
    status = analysis.verification_status if analysis.verification_status in {"running", "completed", "partial", "failed"} else "failed"
    clauses = [clause_response(item) for item in getattr(analysis, "clauses", [])]
    return ContractAnalysisResponse(
        id=analysis.id,
        project_id=analysis.project_id,
        document_id=analysis._response_document_id,
        document_version_id=analysis.document_version_id,
        analysis_version=analysis.analysis_version,
        contract_type=analysis.contract_type,
        parties=metadata.get("parties", []),
        party_details=[ContractPartyResponse.model_validate(item) for item in metadata.get("party_details", []) if isinstance(item, dict)],
        effective_dates=metadata.get("effective_dates", []),
        overall_risk_level=analysis.overall_risk_level or "unknown",
        summary=analysis.summary,
        recommendations=analysis.recommendations if isinstance(analysis.recommendations, list) else [],
        missing_context=metadata.get("missing_context", analysis.missing_context if isinstance(analysis.missing_context, list) else []),
        status=status,
        error_code="contract_analysis_failed" if status == "failed" else None,
        created_at=analysis.created_at,
        clauses=clauses,
        risk_index=calculate_contract_risk_index(clauses),
    )


def clause_response(clause) -> ContractClauseResponse:
    refs = clause.source_refs if isinstance(clause.source_refs, dict) else {}
    detail = refs.get("analysis") if isinstance(refs.get("analysis"), dict) else {}
    evidence = refs.get("evidence") if isinstance(refs.get("evidence"), list) else []
    risk = clause.risk_level if clause.risk_level in {"low", "medium", "high", "critical", "informational", "unknown"} else "unknown"
    state = detail.get("status") if detail.get("status") in {"FOUND", "MISSING", "AMBIGUOUS", "CONTRADICTORY", "OTHER", "NOT_APPLICABLE"} else "FOUND"
    return ContractClauseResponse(
        id=clause.id,
        clause_order=clause.clause_order,
        clause_type=clause.clause_type,
        title=detail.get("title") or clause.heading or clause.clause_type or "Clause analysée",
        status=state,
        source_text=clause.extracted_text,
        source_location=detail.get("source_location"),
        evidence=[ContractEvidenceResponse.model_validate(item) for item in evidence],
        verification_status=detail.get("verification_status") if detail.get("verification_status") in {"VERIFIED", "PARTIALLY_VERIFIED", "UNVERIFIED"} else "UNVERIFIED",
        source_method=detail.get("source_method") if detail.get("source_method") in {"NATIVE", "OCR", "MIXED"} else "NATIVE",
        plain_language_summary=detail.get("plain_language_summary") or clause.finding or "Une disposition a été détectée dans le texte extrait.",
        purpose=detail.get("purpose") or "Le rôle habituel de cette disposition doit être examiné dans le contexte du contrat.",
        what_the_clause_requires=detail.get("what_the_clause_requires"),
        affected_party=detail.get("affected_party"),
        risk_level=risk,
        issues=detail.get("issues", []),
        why_it_matters=detail.get("why_it_matters"),
        ambiguities=detail.get("ambiguities", []),
        missing_elements=detail.get("missing_elements", []),
        potential_consequences=detail.get("potential_consequences", []),
        recommendation=clause.recommendation,
        suggested_revision=detail.get("suggested_revision"),
        related_clauses=detail.get("related_clauses", []),
        confidence=float(clause.confidence) if clause.confidence is not None else None,
        limitations=detail.get("limitations", []),
    )


@router.post("/projects/{project_id}/documents", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: uuid.UUID,
    principal: Principal,
    session: Session,
    background_tasks: BackgroundTasks,
    upload: Annotated[UploadFile, File(...)],
    title: Annotated[str | None, Query(max_length=255)] = None,
    classification: Classification = "confidential",
    visibility: DocumentVisibility = "private",
) -> DocumentUploadResponse:
    document, version = await DocumentService(session).upload_first(principal, project_id, upload, title, classification, visibility)
    if version.malware_scan_status == "clean":
        background_tasks.add_task(process_document_version, version.id)
    return DocumentUploadResponse(document=document_response(document), version=version_response(version))


@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
async def list_project_documents(project_id: uuid.UUID, principal: Principal, session: Session) -> list[DocumentResponse]:
    return [document_response(item) for item in await DocumentService(session).list_for_project(principal, project_id)]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: uuid.UUID, principal: Principal, session: Session) -> DocumentResponse:
    document = await DocumentService(session).get_document(principal, document_id)
    return document_response(document)


@router.post("/documents/{document_id}/versions", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_version(document_id: uuid.UUID, principal: Principal, session: Session, background_tasks: BackgroundTasks, upload: Annotated[UploadFile, File(...)]) -> DocumentUploadResponse:
    document, version = await DocumentService(session).upload_replacement(principal, document_id, upload)
    if version.malware_scan_status == "clean":
        background_tasks.add_task(process_document_version, version.id)
    return DocumentUploadResponse(document=document_response(document), version=version_response(version))


@router.get("/documents/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(document_id: uuid.UUID, principal: Principal, session: Session) -> list[DocumentVersionResponse]:
    return [version_response(item) for item in await DocumentService(session).list_versions(principal, document_id)]


@router.get("/documents/{document_id}/versions/{version_id}", response_model=DocumentVersionResponse)
async def get_document_version(document_id: uuid.UUID, version_id: uuid.UUID, principal: Principal, session: Session) -> DocumentVersionResponse:
    return version_response(await DocumentService(session).get_version(principal, document_id, version_id))


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


@router.post("/documents/{document_id}/versions/{version_id}/processing-jobs/retry", response_model=ProcessingJobResponse)
async def retry_processing_job(document_id: uuid.UUID, version_id: uuid.UUID, principal: Principal, session: Session, background_tasks: BackgroundTasks) -> ProcessingJobResponse:
    await DocumentService(session).retry_extraction(principal, document_id, version_id)
    job = await session.scalar(select(DocumentProcessingJob).where(DocumentProcessingJob.document_version_id == version_id, DocumentProcessingJob.job_type == "extract_text"))
    if job is None:
        raise HTTPException(status_code=404, detail="Document processing job not found")
    background_tasks.add_task(process_document_version, version_id)
    return ProcessingJobResponse(id=job.id, document_version_id=job.document_version_id, job_type="extract_text", idempotency_key=job.idempotency_key, status=job.status)


@router.post("/documents/{document_id}/versions/{version_id}/analyses", response_model=ContractAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def analyze_contract(document_id: uuid.UUID, version_id: uuid.UUID, principal: Principal, session: Session) -> ContractAnalysisResponse:
    return analysis_response(await ContractAnalysisService(session).analyze(principal, document_id, version_id))


@router.get("/contract-analyses/{analysis_id}", response_model=ContractAnalysisResponse)
async def get_contract_analysis(analysis_id: uuid.UUID, principal: Principal, session: Session) -> ContractAnalysisResponse:
    return analysis_response(await ContractAnalysisService(session).get(principal, analysis_id))


@router.get("/documents/{document_id}/analyses", response_model=list[ContractAnalysisResponse])
async def list_contract_analyses(document_id: uuid.UUID, principal: Principal, session: Session) -> list[ContractAnalysisResponse]:
    return [analysis_response(item) for item in await ContractAnalysisService(session).list_for_document(principal, document_id)]
