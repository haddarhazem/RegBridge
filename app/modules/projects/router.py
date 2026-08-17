import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.schemas import ProjectCreate, ProjectMemberInvite, ProjectMemberResponse, ProjectMemberUpdate, ProjectResponse, ProjectUpdate
from app.modules.projects.service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


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
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, principal: Principal, session: Session) -> ProjectResponse:
    project = await ProjectService(session).create(principal, data)
    return project_response(project, True)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, principal: Principal, session: Session) -> ProjectResponse:
    project, membership = await ProjectService(session).get_for_user(principal, project_id)
    return project_response(project, membership)


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
