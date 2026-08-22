"""Authorized generation and progress tracking for launch roadmaps."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import AuditLog
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import ProjectMember
from app.modules.regulatory.assessment_models import RegulatoryAssessment
from app.modules.regulatory.roadmap_generation import generate_typed_items
from app.modules.regulatory.roadmap_models import LaunchRoadmap, LaunchRoadmapItem


class LaunchRoadmapService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _authorize(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> None:
        membership = await self.session.scalar(select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == actor.user_id,
            ProjectMember.status == "active",
        ))
        if membership is None:
            raise HTTPException(status_code=404, detail="Project not found")

    async def generate(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, assessment_id: uuid.UUID) -> LaunchRoadmap:
        await self._authorize(actor, project_id)
        assessment = await self.session.scalar(select(RegulatoryAssessment).where(
            RegulatoryAssessment.id == assessment_id,
            RegulatoryAssessment.project_id == project_id,
        ))
        if assessment is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        if assessment.verification_verdict == "block" or assessment.status != "completed":
            raise HTTPException(status_code=409, detail="A verified assessment is required for roadmap generation")
        items = generate_typed_items(assessment.result or {})
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            await self._authorize(actor, project_id)
            locked = await self.session.scalar(select(RegulatoryAssessment).where(RegulatoryAssessment.id == assessment_id).with_for_update())
            version = (await self.session.scalar(select(func.max(LaunchRoadmap.version)).where(LaunchRoadmap.project_id == project_id)) or 0) + 1
            roadmap = LaunchRoadmap(project_id=project_id, regulatory_assessment_id=assessment_id, version=version, status="active", purpose="creation")
            self.session.add(roadmap)
            await self.session.flush()
            self.session.add_all([LaunchRoadmapItem(roadmap_id=roadmap.id, **item) for item in items])
            self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="roadmap.generated", resource_type="launch_roadmap", resource_id=roadmap.id, project_id=project_id, metadata_json={"assessment_id": str(assessment_id), "version": version, "item_count": len(items)}))
            await self.session.flush()
        return roadmap

    async def _items(self, roadmap_id: uuid.UUID) -> list[LaunchRoadmapItem]:
        return list((await self.session.scalars(select(LaunchRoadmapItem).where(LaunchRoadmapItem.roadmap_id == roadmap_id).order_by(LaunchRoadmapItem.priority_order, LaunchRoadmapItem.id))).all())

    async def latest(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> tuple[LaunchRoadmap | None, list[LaunchRoadmapItem]]:
        await self._authorize(actor, project_id)
        roadmap = await self.session.scalar(select(LaunchRoadmap).where(LaunchRoadmap.project_id == project_id).order_by(LaunchRoadmap.version.desc()).limit(1))
        return (roadmap, await self._items(roadmap.id)) if roadmap else (None, [])

    async def list_versions(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> list[tuple[LaunchRoadmap, list[LaunchRoadmapItem]]]:
        await self._authorize(actor, project_id)
        roadmaps = list((await self.session.scalars(select(LaunchRoadmap).where(LaunchRoadmap.project_id == project_id).order_by(LaunchRoadmap.version))).all())
        return [(roadmap, await self._items(roadmap.id)) for roadmap in roadmaps]

    async def get_version(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, version: int) -> tuple[LaunchRoadmap, list[LaunchRoadmapItem]]:
        await self._authorize(actor, project_id)
        roadmap = await self.session.scalar(select(LaunchRoadmap).where(LaunchRoadmap.project_id == project_id, LaunchRoadmap.version == version))
        if roadmap is None:
            raise HTTPException(status_code=404, detail="Roadmap not found")
        return roadmap, await self._items(roadmap.id)

    async def update_item(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, version: int, item_id: uuid.UUID, status: str) -> LaunchRoadmapItem:
        await self._authorize(actor, project_id)
        if status not in {"pending", "in_progress", "completed", "skipped"}:
            raise HTTPException(status_code=422, detail="Unsupported roadmap item status")
        roadmap = await self.session.scalar(select(LaunchRoadmap).where(LaunchRoadmap.project_id == project_id, LaunchRoadmap.version == version))
        item = await self.session.scalar(select(LaunchRoadmapItem).where(LaunchRoadmapItem.id == item_id, LaunchRoadmapItem.roadmap_id == roadmap.id if roadmap else False))
        if roadmap is None or item is None:
            raise HTTPException(status_code=404, detail="Roadmap item not found")
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            item.status = status
            self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="roadmap.item_status_updated", resource_type="launch_roadmap_item", resource_id=item.id, project_id=project_id, metadata_json={"status": status, "roadmap_version": version}))
        return item
