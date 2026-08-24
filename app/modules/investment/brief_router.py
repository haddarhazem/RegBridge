import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.brief_export_service import BriefExportShareService
from app.modules.investment.brief_schemas import BriefShareCreate, BriefShareResponse, BriefVersionCreate, BriefVersionResponse, OpportunityBriefContent, OpportunityBriefCreate, OpportunityBriefResponse, SharedBriefResponse
from app.modules.investment.brief_service import OpportunityBriefService
from app.modules.investment.brief_verification_schemas import BriefVerificationResponse
from app.modules.sharing.models import InvestorShareGrant

router = APIRouter(prefix="/investment-briefs", tags=["investment-briefs"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


def to_response(run) -> OpportunityBriefResponse:
    content = {key: run.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")}
    return OpportunityBriefResponse(id=run.id, status=run.status, generation_strategy=run.generation_strategy, generation_version=run.generation_version, investor_thesis_version_id=run.investor_thesis_version_id, startup_project_id=run.startup_project_id, matching_run_id=run.matching_run_id, content=OpportunityBriefContent.model_validate(content), created_at=run.created_at)


@router.post("", response_model=OpportunityBriefResponse, status_code=status.HTTP_201_CREATED)
async def create_brief(data: OpportunityBriefCreate, principal: Principal, session: Session):
    return to_response(await OpportunityBriefService(session).create(principal, data.startup_project_id, data.investor_thesis_version_id, data.matching_run_id))


@router.get("/shared-with-me", response_model=list[SharedBriefResponse])
async def list_shared_briefs(principal: Principal, session: Session):
    result = []
    for grant, version in await BriefExportShareService(session).list_shared(principal):
        result.append(SharedBriefResponse(share_id=grant.id, brief_run_id=version.brief_run_id, version_id=version.id, version_number=version.version_number, status="APPROVED", scope="READ", content=version.content, created_at=version.created_at))
    return result


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
    current = await OpportunityBriefService(session).current_version(principal, run_id)
    runs = list((await session.scalars(select(BriefVerificationRun).where(BriefVerificationRun.brief_version_id == current.id).order_by(BriefVerificationRun.created_at))).all())
    result = []
    for run in runs:
        claims = list((await session.scalars(select(BriefClaimVerification).where(BriefClaimVerification.verification_run_id == run.id).order_by(BriefClaimVerification.id))).all())
        result.append(BriefVerificationResponse(id=run.id, brief_run_id=run_id, brief_version_id=run.brief_version_id, verifier_strategy=run.verifier_strategy, verifier_version=run.verifier_version, status=run.status, created_at=run.created_at, claims=claims))
    return result


@router.get("/{run_id}/versions", response_model=list[BriefVersionResponse])
async def list_brief_versions(run_id: uuid.UUID, principal: Principal, session: Session):
    return await OpportunityBriefService(session).list_versions(principal, run_id)


@router.get("/{run_id}/versions/current", response_model=BriefVersionResponse)
async def get_current_brief_version(run_id: uuid.UUID, principal: Principal, session: Session):
    version = await OpportunityBriefService(session).current_version(principal, run_id)
    return await OpportunityBriefService(session).version_response(version)


@router.get("/{run_id}/versions/{version_id}", response_model=BriefVersionResponse)
async def get_brief_version(run_id: uuid.UUID, version_id: uuid.UUID, principal: Principal, session: Session):
    service = OpportunityBriefService(session)
    version = await service._authorized_version(principal, version_id)
    if version.brief_run_id != run_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Opportunity brief version not found")
    return await service.version_response(version)


@router.post("/{run_id}/versions", response_model=BriefVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_brief_version(run_id: uuid.UUID, data: BriefVersionCreate, principal: Principal, session: Session):
    return await OpportunityBriefService(session).create_version(principal, run_id, data)


@router.post("/{run_id}/versions/{version_id}/verify", response_model=BriefVerificationResponse)
async def verify_brief_version(run_id: uuid.UUID, version_id: uuid.UUID, principal: Principal, session: Session):
    return await OpportunityBriefService(session).verify(principal, run_id, version_id)


@router.post("/{run_id}/versions/{version_id}/approve", response_model=BriefVersionResponse)
async def approve_brief_version(run_id: uuid.UUID, version_id: uuid.UUID, principal: Principal, session: Session):
    service = OpportunityBriefService(session)
    version = await service._authorized_version(principal, version_id)
    if version.brief_run_id != run_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Opportunity brief version not found")
    return await service.approve_version(principal, version_id)


def _pdf_response(pdf: bytes, version_number: int) -> Response:
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="regbridge-opportunity-brief-v{version_number}.pdf"'})


@router.get("/{run_id}/versions/{version_id}/export.pdf", response_class=Response)
async def export_brief_pdf(run_id: uuid.UUID, version_id: uuid.UUID, principal: Principal, session: Session):
    pdf, version_number, _ = await BriefExportShareService(session).export_owner(principal, run_id, version_id)
    return _pdf_response(pdf, version_number)


@router.post("/{run_id}/versions/{version_id}/shares", response_model=BriefShareResponse, status_code=status.HTTP_201_CREATED)
async def share_brief_version(run_id: uuid.UUID, version_id: uuid.UUID, data: BriefShareCreate, principal: Principal, session: Session):
    grant = await BriefExportShareService(session).create_share(principal, run_id, version_id, data.recipient_user_id)
    return BriefShareResponse(id=grant.id, version_id=version_id, recipient_user_id=grant.recipient_user_id, scope=grant.scope, status=grant.status, created_at=grant.granted_at, revoked_at=grant.revoked_at)


@router.get("/{run_id}/versions/{version_id}/shares/{grant_id}", response_model=BriefShareResponse)
async def get_brief_share(run_id: uuid.UUID, version_id: uuid.UUID, grant_id: uuid.UUID, principal: Principal, session: Session):
    service = BriefExportShareService(session)
    run, version = await service._owner_version(principal, run_id, version_id)
    grant = await session.scalar(select(InvestorShareGrant).where(InvestorShareGrant.id == grant_id, InvestorShareGrant.project_id == run.startup_project_id, InvestorShareGrant.resource_id == version.id, InvestorShareGrant.resource_type == "INVESTOR_OPPORTUNITY_BRIEF_VERSION"))
    if grant is None:
        raise HTTPException(status_code=404, detail="Share grant not found")
    return BriefShareResponse(id=grant.id, version_id=version.id, recipient_user_id=grant.recipient_user_id, scope=grant.scope, status=grant.status, created_at=grant.granted_at, revoked_at=grant.revoked_at)


@router.delete("/{run_id}/versions/{version_id}/shares/{grant_id}", response_model=BriefShareResponse)
async def revoke_brief_share(run_id: uuid.UUID, version_id: uuid.UUID, grant_id: uuid.UUID, principal: Principal, session: Session):
    grant = await BriefExportShareService(session).revoke_share(principal, run_id, version_id, grant_id)
    return BriefShareResponse(id=grant.id, version_id=version_id, recipient_user_id=grant.recipient_user_id, scope=grant.scope, status=grant.status, created_at=grant.granted_at, revoked_at=grant.revoked_at)


@router.get("/shared/{version_id}", response_model=SharedBriefResponse)
async def get_shared_brief(version_id: uuid.UUID, principal: Principal, session: Session):
    grant, run, version = await BriefExportShareService(session).shared_version(principal, version_id)
    content = OpportunityBriefContent.model_validate({key: version.content[key] for key in ("executive_summary", "thesis_fit", "investment_highlights", "missing_information", "disclaimer")})
    return SharedBriefResponse(share_id=grant.id, brief_run_id=run.id, version_id=version.id, version_number=version.version_number, status="APPROVED", scope="READ", content=content, created_at=version.created_at)


@router.get("/shared/{version_id}/export.pdf", response_class=Response)
async def export_shared_brief_pdf(version_id: uuid.UUID, principal: Principal, session: Session):
    pdf, version_number, _ = await BriefExportShareService(session).export_shared(principal, version_id)
    return _pdf_response(pdf, version_number)
