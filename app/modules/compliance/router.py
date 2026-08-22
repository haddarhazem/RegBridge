import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.compliance.schemas import AdoptionCreate, AdoptionResponse, ControlStatePatch, EvidenceCreate, EvidenceResponse, EvidenceRevoke, FrameworkResponse, FrameworkVersionResponse, ProjectControlResponse, ScoreCalculateRequest, ScoreResponse
from app.modules.compliance.service import ComplianceService
from app.modules.compliance.score_service import ComplianceScoreService
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal

router = APIRouter(tags=["compliance"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


def framework_response(item) -> FrameworkResponse:
    return FrameworkResponse(id=item.id, stable_key=item.stable_key, name=item.name, versions=[FrameworkVersionResponse.model_validate(version) for version in getattr(item, "versions", [])])


def control_response(item) -> ProjectControlResponse:
    return ProjectControlResponse(id=item.id, project_id=item.project_id, framework_version_id=item.framework_version_id, control_definition_id=item.control_definition_id, status=item.status, applicability=item.applicability, notes=item.notes, created_at=item.created_at, updated_at=item.updated_at, definition=item.definition)


@router.get("/compliance/frameworks", response_model=list[FrameworkResponse])
async def list_frameworks(session: Session) -> list[FrameworkResponse]:
    return [framework_response(item) for item in await ComplianceService(session).frameworks()]


@router.get("/projects/{project_id}/compliance/controls", response_model=list[ProjectControlResponse])
async def list_controls(project_id: uuid.UUID, principal: Principal, session: Session) -> list[ProjectControlResponse]:
    return [control_response(item) for item in await ComplianceService(session).controls(principal, project_id)]


@router.post("/projects/{project_id}/compliance/adoptions", response_model=AdoptionResponse, status_code=status.HTTP_201_CREATED)
async def adopt_framework(project_id: uuid.UUID, data: AdoptionCreate, principal: Principal, session: Session) -> AdoptionResponse:
    return AdoptionResponse.model_validate(await ComplianceService(session).adopt(principal, project_id, data))


@router.patch("/projects/{project_id}/compliance/controls/{control_id}", response_model=ProjectControlResponse)
async def update_control(project_id: uuid.UUID, control_id: uuid.UUID, data: ControlStatePatch, principal: Principal, session: Session) -> ProjectControlResponse:
    return control_response(await ComplianceService(session).update_control(principal, project_id, control_id, data))


@router.post("/projects/{project_id}/compliance/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def attach_evidence(project_id: uuid.UUID, data: EvidenceCreate, principal: Principal, session: Session) -> EvidenceResponse:
    return EvidenceResponse.model_validate(await ComplianceService(session).attach_evidence(principal, project_id, data))


@router.post("/projects/{project_id}/compliance/evidence/{evidence_id}/revoke", response_model=EvidenceResponse)
async def revoke_evidence(project_id: uuid.UUID, evidence_id: uuid.UUID, data: EvidenceRevoke, principal: Principal, session: Session) -> EvidenceResponse:
    return EvidenceResponse.model_validate(await ComplianceService(session).revoke_evidence(principal, project_id, evidence_id, data))


@router.get("/projects/{project_id}/compliance/controls/{control_id}/evidence", response_model=list[EvidenceResponse])
async def control_evidence(project_id: uuid.UUID, control_id: uuid.UUID, principal: Principal, session: Session) -> list[EvidenceResponse]:
    return [EvidenceResponse.model_validate(item) for item in await ComplianceService(session).evidence_for_control(principal, project_id, control_id)]


@router.post("/projects/{project_id}/compliance/scores", response_model=ScoreResponse, status_code=status.HTTP_201_CREATED)
async def calculate_score(project_id: uuid.UUID, data: ScoreCalculateRequest, principal: Principal, session: Session) -> ScoreResponse:
    return ScoreResponse.model_validate(await ComplianceScoreService(session).calculate_current(principal, project_id, data.framework_version_id, data.method_version))


@router.get("/projects/{project_id}/compliance/scores/latest", response_model=ScoreResponse)
async def latest_score(project_id: uuid.UUID, principal: Principal, session: Session, framework_version_id: uuid.UUID | None = None) -> ScoreResponse:
    return ScoreResponse.model_validate(await ComplianceScoreService(session).latest(principal, project_id, framework_version_id))


@router.get("/projects/{project_id}/compliance/scores/history", response_model=list[ScoreResponse])
async def score_history(project_id: uuid.UUID, principal: Principal, session: Session, framework_version_id: uuid.UUID | None = None) -> list[ScoreResponse]:
    return [ScoreResponse.model_validate(item) for item in await ComplianceScoreService(session).history(principal, project_id, framework_version_id)]


@router.get("/projects/{project_id}/compliance/scores/{score_id}", response_model=ScoreResponse)
async def score_breakdown(project_id: uuid.UUID, score_id: uuid.UUID, principal: Principal, session: Session) -> ScoreResponse:
    return ScoreResponse.model_validate(await ComplianceScoreService(session).get(principal, project_id, score_id))
