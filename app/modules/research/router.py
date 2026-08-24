import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.research.schemas import ResearcherProfileResponse, ResearcherProfileUpsert, ResearchOutputCreate, ResearchOutputResponse, ResearchOutputVersionResponse
from app.modules.research.service import ResearchService, missing_rights_fields

router = APIRouter(tags=["research"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


def profile_response(profile) -> ResearcherProfileResponse:
    return ResearcherProfileResponse(id=profile.id, user_id=profile.user_id, affiliation=profile.affiliation, scientific_domains=profile.scientific_domains, created_at=profile.created_at, updated_at=profile.updated_at)


def output_response(output) -> ResearchOutputResponse:
    missing = missing_rights_fields(output.rights_holder, output.licence)
    return ResearchOutputResponse(id=output.id, researcher_profile_id=output.researcher_profile_id, title=output.title, authors=output.authors, rights_holder=output.rights_holder, licence=output.licence, visibility=output.visibility, rights_metadata_status=output.rights_metadata_status, missing_rights_fields=missing, publication_ready=output.publication_ready, created_at=output.created_at, updated_at=output.updated_at)


def version_response(version, document_version) -> ResearchOutputVersionResponse:
    return ResearchOutputVersionResponse(id=version.id, research_output_id=version.research_output_id, version_number=version.version_number, uploaded_by_user_id=version.uploaded_by_user_id, document_version_id=version.document_version_id, mime_type=document_version.mime_type, size_bytes=document_version.size_bytes, content_hash=version.content_hash, original_filename=document_version.original_filename, created_at=version.created_at)


@router.get("/researcher/profile", response_model=ResearcherProfileResponse)
async def get_researcher_profile(principal: Principal, session: Session):
    return profile_response(await ResearchService(session).get_profile(principal))


@router.put("/researcher/profile", response_model=ResearcherProfileResponse)
async def upsert_researcher_profile(data: ResearcherProfileUpsert, principal: Principal, session: Session):
    return profile_response(await ResearchService(session).upsert_profile(principal, data))


@router.post("/research/outputs", response_model=ResearchOutputResponse, status_code=status.HTTP_201_CREATED)
async def create_research_output(data: ResearchOutputCreate, principal: Principal, session: Session):
    return output_response(await ResearchService(session).create_output(principal, data))


@router.get("/research/outputs", response_model=list[ResearchOutputResponse])
async def list_research_outputs(principal: Principal, session: Session):
    return [output_response(item) for item in await ResearchService(session).list_outputs(principal)]


@router.get("/research/outputs/{output_id}", response_model=ResearchOutputResponse)
async def get_research_output(output_id: uuid.UUID, principal: Principal, session: Session):
    return output_response(await ResearchService(session).get_output(principal, output_id))


@router.post("/research/outputs/{output_id}/versions", response_model=ResearchOutputVersionResponse, status_code=status.HTTP_201_CREATED)
async def upload_research_output_version(output_id: uuid.UUID, principal: Principal, session: Session, upload: Annotated[UploadFile, File(...)]):
    _, version, document_version = await ResearchService(session).upload_version(principal, output_id, upload)
    return version_response(version, document_version)


@router.get("/research/outputs/{output_id}/versions", response_model=list[ResearchOutputVersionResponse])
async def list_research_output_versions(output_id: uuid.UUID, principal: Principal, session: Session):
    return [version_response(version, document_version) for version, document_version in await ResearchService(session).list_versions(principal, output_id)]


@router.get("/research/outputs/{output_id}/versions/current", response_model=ResearchOutputVersionResponse)
async def get_current_research_output_version(output_id: uuid.UUID, principal: Principal, session: Session):
    version, document_version = await ResearchService(session).current_version(principal, output_id)
    return version_response(version, document_version)


@router.get("/research/outputs/{output_id}/versions/{version_id}", response_model=ResearchOutputVersionResponse)
async def get_research_output_version(output_id: uuid.UUID, version_id: uuid.UUID, principal: Principal, session: Session):
    version, document_version = await ResearchService(session).get_version(principal, output_id, version_id)
    return version_response(version, document_version)


@router.get("/research/outputs/{output_id}/versions/{version_id}/download")
async def download_research_output_version(output_id: uuid.UUID, version_id: uuid.UUID, principal: Principal, session: Session):
    version, stream = await ResearchService(session).download(principal, output_id, version_id)
    filename = quote(version.original_filename.replace("\r", "").replace("\n", ""))
    return StreamingResponse(stream, media_type=version.mime_type, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"})
