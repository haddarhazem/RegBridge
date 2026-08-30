import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.onboarding import confirmed_fields, next_questions
from app.modules.projects.profile_schemas import PublicStartupProfileResponse, StartupProfileFieldResponse, StartupProfileResponse, StartupProfileRevisionResponse, StartupProfilePatch
from app.modules.projects.profile_service import StartupProfileService
from app.modules.projects.schemas import IdeaOnboardingResponse, IdeaOnboardingUpdate, IdeaProjectCreate, ProjectCreate, ProjectFactCorrection, ProjectFactResponse, ProjectLifecycleHistoryResponse, ProjectLifecycleTransition, ProjectMemberInvite, ProjectMemberResponse, ProjectMemberUpdate, ProjectResponse, ProjectUpdate
from app.modules.projects.service import ProjectService
from app.modules.projects.matching_service import ResearchMatchingService
from app.modules.projects.schemas import ResearchNeedPayload, ResearchNeedResponse, ResearchMatchRunResponse, ResearchMatchResultResponse

router = APIRouter(prefix="/projects", tags=["projects"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]

def need_response(need, version):
    return ResearchNeedResponse(id=need.id, project_id=need.project_id, version_id=version.id, version_number=version.version_number, domains=version.domains, technologies=version.technologies, research_problem=version.research_problem, keywords=version.keywords)

def run_response(run):
    return ResearchMatchRunResponse(id=run.id, project_id=run.project_id, need_version_id=run.need_version_id, algorithm_id=run.algorithm_id, algorithm_version=run.algorithm_version, top_k=run.top_k, status=run.status, results=[ResearchMatchResultResponse(id=x.id, research_discovery_version_id=x.research_discovery_version_id, rank=x.rank, ranking_score=x.ranking_score, status=x.status, reason_codes=x.reason_codes, startup_field_refs=x.startup_field_refs, research_field_refs=x.research_field_refs, uncertainty_codes=x.uncertainty_codes) for x in getattr(run,"results",[])])


def project_response(project, membership) -> ProjectResponse:
    is_member = membership is True or (membership is not None and getattr(membership, "status", None) == "active")
    if not is_member:
        return ProjectResponse(id=project.id, project_type=project.project_type, display_name=project.display_name, visibility=project.visibility, is_member=False)
    return ProjectResponse(
        id=project.id,
        project_type=project.project_type,
        display_name=project.display_name,
        visibility=project.visibility,
        is_member=True,
        raw_description=project.raw_description,
        user_goal=project.user_goal,
        current_progress=project.current_progress,
        country_code=project.country_code,
        target_market=project.target_market,
        language=project.language,
        owner_user_id=project.owner_user_id,
        activity=getattr(project, "activity", None),
        sector=getattr(project, "sector", None),
        technology=getattr(project, "technology", None),
        data=getattr(project, "data_context", None),
        location=getattr(project, "location", None),
        onboarding_status=getattr(project, "onboarding_status", None),
        confirmed_fields=confirmed_fields(project) if hasattr(project, "confirmed_fields") else [],
    )


def fact_response(fact) -> ProjectFactResponse:
    return ProjectFactResponse(
        id=fact.id,
        project_id=fact.project_id,
        domain=fact.domain,
        value=fact.value,
        origin=fact.origin,
        status=fact.status,
        provenance=fact.provenance,
        uncertainty=fact.uncertainty,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, principal: Principal, session: Session) -> ProjectResponse:
    project = await ProjectService(session).create(principal, data)
    return project_response(project, True)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(principal: Principal, session: Session) -> list[ProjectResponse]:
    projects = await ProjectService(session).list_for_user(principal)
    return [project_response(project, membership) for project, membership in projects]

@router.post("/{project_id}/research-needs", response_model=ResearchNeedResponse, status_code=status.HTTP_201_CREATED)
async def create_research_need(project_id: uuid.UUID, data: ResearchNeedPayload, principal: Principal, session: Session):
    return need_response(*await ResearchMatchingService(session).create_need(principal, project_id, data))

@router.post("/{project_id}/research-needs/{need_id}/versions", response_model=ResearchNeedResponse, status_code=status.HTTP_201_CREATED)
async def version_research_need(project_id: uuid.UUID, need_id: uuid.UUID, data: ResearchNeedPayload, principal: Principal, session: Session):
    return need_response(*await ResearchMatchingService(session).version_need(principal, project_id, need_id, data))

@router.post("/{project_id}/research-needs/{need_id}/match", response_model=ResearchMatchRunResponse, status_code=status.HTTP_201_CREATED)
async def run_research_matching(project_id: uuid.UUID, need_id: uuid.UUID, principal: Principal, session: Session):
    service = ResearchMatchingService(session)
    run = await service.run(principal, project_id, need_id)
    return run_response(await service.get_run(principal, project_id, run.id))

@router.get("/{project_id}/research-match-runs/{run_id}", response_model=ResearchMatchRunResponse)
async def get_research_matching_run(project_id: uuid.UUID, run_id: uuid.UUID, principal: Principal, session: Session):
    return run_response(await ResearchMatchingService(session).get_run(principal, project_id, run_id))


@router.post("/ideas", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_idea_project(data: IdeaProjectCreate, principal: Principal, session: Session) -> ProjectResponse:
    project = await ProjectService(session).create_idea(principal, data)
    return project_response(project, True)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, principal: Principal, session: Session) -> ProjectResponse:
    project, membership = await ProjectService(session).get_for_user(principal, project_id)
    return project_response(project, membership)


@router.get("/{project_id}/onboarding", response_model=IdeaOnboardingResponse)
async def get_onboarding(project_id: uuid.UUID, principal: Principal, session: Session) -> IdeaOnboardingResponse:
    project = await ProjectService(session).get_idea_for_user(principal, project_id)
    return IdeaOnboardingResponse(
        project_id=project.id,
        status=project.onboarding_status,
        confirmed_fields=confirmed_fields(project),
        next_questions=next_questions(project),
    )


@router.patch("/{project_id}/onboarding", response_model=IdeaOnboardingResponse)
async def update_onboarding(project_id: uuid.UUID, data: IdeaOnboardingUpdate, principal: Principal, session: Session) -> IdeaOnboardingResponse:
    project = await ProjectService(session).update_onboarding(principal, project_id, data)
    return IdeaOnboardingResponse(
        project_id=project.id,
        status=project.onboarding_status,
        confirmed_fields=confirmed_fields(project),
        next_questions=next_questions(project),
    )


@router.post("/{project_id}/transition", response_model=ProjectResponse)
async def transition_project(project_id: uuid.UUID, data: ProjectLifecycleTransition, principal: Principal, session: Session) -> ProjectResponse:
    project = await ProjectService(session).transition_project(principal, project_id, data.target_type)
    return project_response(project, True)


def startup_profile_response(project, profile, fields) -> StartupProfileResponse:
    return StartupProfileResponse(
        project_id=project.id,
        project_type=project.project_type,
        revision=profile.current_revision if profile is not None else 0,
        fields=[StartupProfileFieldResponse(field_name=field.field_name, section=field.section, value=field.value, visibility=field.visibility) for field in fields],
    )


@router.get("/{project_id}/startup-profile", response_model=StartupProfileResponse)
async def get_startup_profile(project_id: uuid.UUID, principal: Principal, session: Session) -> StartupProfileResponse:
    project, profile, fields = await StartupProfileService(session).get_internal(principal, project_id)
    return startup_profile_response(project, profile, fields)


@router.patch("/{project_id}/startup-profile", response_model=StartupProfileResponse)
async def update_startup_profile(project_id: uuid.UUID, data: StartupProfilePatch, principal: Principal, session: Session) -> StartupProfileResponse:
    project, profile, fields = await StartupProfileService(session).update(principal, project_id, data)
    return startup_profile_response(project, profile, fields)


@router.get("/{project_id}/startup-profile/history", response_model=list[StartupProfileRevisionResponse])
async def get_startup_profile_history(project_id: uuid.UUID, principal: Principal, session: Session) -> list[StartupProfileRevisionResponse]:
    revisions = await StartupProfileService(session).history(principal, project_id)
    return [StartupProfileRevisionResponse(revision=revision.revision_number, snapshot=revision.snapshot, changed_by_user_id=revision.changed_by_user_id, created_at=revision.created_at) for revision in revisions]


@router.get("/{project_id}/public-profile", response_model=PublicStartupProfileResponse)
async def get_public_startup_profile(project_id: uuid.UUID, session: Session) -> PublicStartupProfileResponse:
    return PublicStartupProfileResponse(fields=await StartupProfileService(session).get_public(project_id))


@router.get("/{project_id}/lifecycle-history", response_model=list[ProjectLifecycleHistoryResponse])
async def lifecycle_history(project_id: uuid.UUID, principal: Principal, session: Session) -> list[ProjectLifecycleHistoryResponse]:
    records = await ProjectService(session).lifecycle_history(principal, project_id)
    return [ProjectLifecycleHistoryResponse(id=record.id, project_id=record.project_id, actor_user_id=record.actor_user_id, from_type=record.metadata_json["from_type"], to_type=record.metadata_json["to_type"], created_at=record.created_at) for record in records]


@router.post("/{project_id}/facts/infer", response_model=list[ProjectFactResponse])
async def infer_project_facts(project_id: uuid.UUID, principal: Principal, session: Session) -> list[ProjectFactResponse]:
    facts = await ProjectService(session).infer_facts(principal, project_id)
    return [fact_response(fact) for fact in facts]


@router.get("/{project_id}/facts", response_model=list[ProjectFactResponse])
async def list_project_facts(project_id: uuid.UUID, principal: Principal, session: Session) -> list[ProjectFactResponse]:
    facts = await ProjectService(session).list_facts(principal, project_id)
    return [fact_response(fact) for fact in facts]


@router.post("/{project_id}/facts/{fact_id}/confirm", response_model=ProjectFactResponse)
async def confirm_project_fact(project_id: uuid.UUID, fact_id: uuid.UUID, principal: Principal, session: Session) -> ProjectFactResponse:
    return fact_response(await ProjectService(session).confirm_fact(principal, project_id, fact_id))


@router.patch("/{project_id}/facts/{fact_id}", response_model=ProjectFactResponse)
async def correct_project_fact(project_id: uuid.UUID, fact_id: uuid.UUID, data: ProjectFactCorrection, principal: Principal, session: Session) -> ProjectFactResponse:
    return fact_response(await ProjectService(session).correct_fact(principal, project_id, fact_id, data.value))


@router.delete("/{project_id}/facts/{fact_id}", response_model=ProjectFactResponse)
async def reject_project_fact(project_id: uuid.UUID, fact_id: uuid.UUID, principal: Principal, session: Session) -> ProjectFactResponse:
    return fact_response(await ProjectService(session).reject_fact(principal, project_id, fact_id))


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: uuid.UUID, data: ProjectUpdate, principal: Principal, session: Session) -> ProjectResponse:
    project = await ProjectService(session).update(principal, project_id, data)
    membership = await ProjectService(session)._membership(project_id, principal.user_id, active_only=True)
    return project_response(project, membership)


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_members(project_id: uuid.UUID, principal: Principal, session: Session) -> list[ProjectMemberResponse]:
    members = await ProjectService(session).list_members(principal, project_id)
    return [ProjectMemberResponse(user_id=m.user_id, first_name=None, last_name=None, member_role=m.member_role, status=m.status, joined_at=m.joined_at) for m in members]


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(project_id: uuid.UUID, data: ProjectMemberInvite, principal: Principal, session: Session) -> ProjectMemberResponse:
    member = await ProjectService(session).invite(principal, project_id, data)
    return ProjectMemberResponse(user_id=member.user_id, first_name=None, last_name=None, member_role=member.member_role, status=member.status, joined_at=member.joined_at)


@router.post("/{project_id}/members/me/accept", response_model=ProjectMemberResponse)
async def accept_invitation(project_id: uuid.UUID, principal: Principal, session: Session) -> ProjectMemberResponse:
    member = await ProjectService(session).accept(principal, project_id)
    return ProjectMemberResponse(user_id=member.user_id, first_name=None, last_name=None, member_role=member.member_role, status=member.status, joined_at=member.joined_at)


@router.patch("/{project_id}/members/{user_id}", response_model=ProjectMemberResponse)
async def change_member_role(project_id: uuid.UUID, user_id: uuid.UUID, data: ProjectMemberUpdate, principal: Principal, session: Session) -> ProjectMemberResponse:
    member = await ProjectService(session).change_role(principal, project_id, user_id, data)
    return ProjectMemberResponse(user_id=member.user_id, first_name=None, last_name=None, member_role=member.member_role, status=member.status, joined_at=member.joined_at)


@router.delete("/{project_id}/members/{user_id}", response_model=ProjectMemberResponse)
async def revoke_member(project_id: uuid.UUID, user_id: uuid.UUID, principal: Principal, session: Session) -> ProjectMemberResponse:
    member = await ProjectService(session).revoke(principal, project_id, user_id)
    return ProjectMemberResponse(user_id=member.user_id, first_name=None, last_name=None, member_role=member.member_role, status=member.status, joined_at=member.joined_at)
