"""Authorized project regulatory-assessment API."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.regulatory.assessment_contracts import AssessmentGenerateRequest, RegulatoryAssessmentResponse
from app.modules.regulatory.assessment_service import RegulatoryAssessmentService

router = APIRouter(prefix="/projects", tags=["regulatory-assessments"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


def response(assessment) -> RegulatoryAssessmentResponse:
    internal_result = dict(assessment.result or {})
    provenance = {str(item.get("point_id")): str(item.get("organization")) for item in (assessment.source_provenance or []) if item.get("point_id") and item.get("organization")}
    for field in ("obligations", "recommendations", "uncertainties"):
        conclusions = []
        for item in internal_result.get(field, []):
            public_item = dict(item)
            public_item["source_refs"] = list(dict.fromkeys(provenance.get(str(ref), str(ref)) for ref in item.get("source_refs", []) if provenance.get(str(ref))))
            conclusions.append(public_item)
        internal_result[field] = conclusions
    return RegulatoryAssessmentResponse(
        id=assessment.id, project_id=assessment.project_id, version=assessment.version, snapshot_id=assessment.snapshot_id,
        status=assessment.status, result=internal_result, verification_verdict=assessment.verification_verdict,
        verification_reasons=assessment.verification_reasons, created_at=assessment.created_at,
    )


@router.post("/{project_id}/assessments", response_model=RegulatoryAssessmentResponse)
async def generate_assessment(project_id: uuid.UUID, data: AssessmentGenerateRequest, principal: Principal, session: Session) -> RegulatoryAssessmentResponse:
    return response(await RegulatoryAssessmentService(session).generate(principal, project_id, data.question))


@router.get("/{project_id}/assessments/latest", response_model=RegulatoryAssessmentResponse | None)
async def latest_assessment(project_id: uuid.UUID, principal: Principal, session: Session):
    assessment = await RegulatoryAssessmentService(session).latest(principal, project_id)
    return response(assessment) if assessment else None


@router.get("/{project_id}/assessments", response_model=list[RegulatoryAssessmentResponse])
async def list_assessments(project_id: uuid.UUID, principal: Principal, session: Session):
    return [response(item) for item in await RegulatoryAssessmentService(session).list_versions(principal, project_id)]


@router.get("/{project_id}/assessments/{version}", response_model=RegulatoryAssessmentResponse)
async def get_assessment(project_id: uuid.UUID, version: int, principal: Principal, session: Session):
    return response(await RegulatoryAssessmentService(session).get_version(principal, project_id, version))
