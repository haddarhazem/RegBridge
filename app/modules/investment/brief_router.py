import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.brief_schemas import OpportunityBriefContent, OpportunityBriefCreate, OpportunityBriefResponse
from app.modules.investment.brief_service import OpportunityBriefService
from app.modules.investment.brief_verification_schemas import BriefVerificationResponse

router = APIRouter(prefix="/investment-briefs", tags=["investment-briefs"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


def to_response(run) -> OpportunityBriefResponse:
    content = {key: run.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")}
    return OpportunityBriefResponse(id=run.id, status=run.status, generation_strategy=run.generation_strategy, generation_version=run.generation_version, investor_thesis_version_id=run.investor_thesis_version_id, startup_project_id=run.startup_project_id, matching_run_id=run.matching_run_id, content=OpportunityBriefContent.model_validate(content), created_at=run.created_at)


@router.post("", response_model=OpportunityBriefResponse, status_code=status.HTTP_201_CREATED)
async def create_brief(data: OpportunityBriefCreate, principal: Principal, session: Session):
    return to_response(await OpportunityBriefService(session).create(principal, data.startup_project_id, data.investor_thesis_version_id, data.matching_run_id))


@router.get("/{run_id}", response_model=OpportunityBriefResponse)
async def get_brief(run_id: uuid.UUID, principal: Principal, session: Session):
    return to_response(await OpportunityBriefService(session).get(principal, run_id))


@router.post("/{run_id}/verify", response_model=BriefVerificationResponse)
async def verify_brief(run_id: uuid.UUID, principal: Principal, session: Session):
    return await OpportunityBriefService(session).verify(principal, run_id)


@router.get("/{run_id}/verification", response_model=list[BriefVerificationResponse])
async def get_verifications(run_id: uuid.UUID, principal: Principal, session: Session):
    await OpportunityBriefService(session).get(principal, run_id)
    from sqlalchemy import select
    from app.modules.investment.brief_verification_models import BriefVerificationRun, BriefClaimVerification
    runs = list((await session.scalars(select(BriefVerificationRun).where(BriefVerificationRun.brief_run_id == run_id).order_by(BriefVerificationRun.created_at))).all())
    result = []
    for run in runs:
        claims = list((await session.scalars(select(BriefClaimVerification).where(BriefClaimVerification.verification_run_id == run.id).order_by(BriefClaimVerification.id))).all())
        result.append(BriefVerificationResponse(id=run.id, brief_run_id=run_id, verifier_strategy=run.verifier_strategy, verifier_version=run.verifier_version, status=run.status, created_at=run.created_at, claims=claims))
    return result
