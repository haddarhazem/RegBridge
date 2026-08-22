"""Authorized launch-roadmap API."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.regulatory.roadmap_contracts import LaunchRoadmapResponse, RoadmapGenerateRequest, RoadmapItemResponse, RoadmapItemStatusUpdate
from app.modules.regulatory.roadmap_service import LaunchRoadmapService

router = APIRouter(prefix="/projects", tags=["launch-roadmaps"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


def response(roadmap, items) -> LaunchRoadmapResponse:
    return LaunchRoadmapResponse(
        id=roadmap.id, project_id=roadmap.project_id, regulatory_assessment_id=roadmap.regulatory_assessment_id,
        version=roadmap.version, status=roadmap.status,
        items=[RoadmapItemResponse(
            id=item.id, roadmap_id=item.roadmap_id, item_type=item.item_type, title=item.title,
            justification=item.justification, priority_order=item.priority_order, status=item.status,
            source_conclusion_refs=item.source_conclusion_refs, dependency_item_refs=item.dependency_item_refs,
            created_at=item.created_at, updated_at=item.updated_at,
        ) for item in items],
        created_at=roadmap.created_at,
    )


@router.post("/{project_id}/roadmaps", response_model=LaunchRoadmapResponse)
async def generate_roadmap(project_id: uuid.UUID, data: RoadmapGenerateRequest, principal: Principal, session: Session):
    roadmap = await LaunchRoadmapService(session).generate(principal, project_id, data.regulatory_assessment_id)
    return response(roadmap, await LaunchRoadmapService(session)._items(roadmap.id))


@router.get("/{project_id}/roadmaps/latest", response_model=LaunchRoadmapResponse | None)
async def latest_roadmap(project_id: uuid.UUID, principal: Principal, session: Session):
    roadmap, items = await LaunchRoadmapService(session).latest(principal, project_id)
    return response(roadmap, items) if roadmap else None


@router.get("/{project_id}/roadmaps", response_model=list[LaunchRoadmapResponse])
async def list_roadmaps(project_id: uuid.UUID, principal: Principal, session: Session):
    return [response(roadmap, items) for roadmap, items in await LaunchRoadmapService(session).list_versions(principal, project_id)]


@router.get("/{project_id}/roadmaps/{version}", response_model=LaunchRoadmapResponse)
async def get_roadmap(project_id: uuid.UUID, version: int, principal: Principal, session: Session):
    roadmap, items = await LaunchRoadmapService(session).get_version(principal, project_id, version)
    return response(roadmap, items)


@router.patch("/{project_id}/roadmaps/{version}/items/{item_id}", response_model=RoadmapItemResponse)
async def update_roadmap_item(project_id: uuid.UUID, version: int, item_id: uuid.UUID, data: RoadmapItemStatusUpdate, principal: Principal, session: Session):
    item = await LaunchRoadmapService(session).update_item(principal, project_id, version, item_id, data.status)
    return RoadmapItemResponse(
        id=item.id, roadmap_id=item.roadmap_id, item_type=item.item_type, title=item.title, justification=item.justification,
        priority_order=item.priority_order, status=item.status, source_conclusion_refs=item.source_conclusion_refs,
        dependency_item_refs=item.dependency_item_refs, created_at=item.created_at, updated_at=item.updated_at,
    )
