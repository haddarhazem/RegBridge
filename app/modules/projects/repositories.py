"""Focused project reads used by authorized AI context construction."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.context import ProjectContextProjection, ProjectFactProjection
from app.modules.projects.models import Project, ProjectFact, ProjectMember


class ProjectContextRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def has_active_membership(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        membership = await self.session.scalar(
            select(ProjectMember.project_id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
                ProjectMember.status == "active",
            )
        )
        return membership is not None

    async def load_minimal_projection(self, project_id: uuid.UUID) -> ProjectContextProjection | None:
        row = await self.session.execute(
            select(
                Project.project_type,
                Project.country_code,
                Project.user_goal,
                Project.activity,
                Project.sector,
                Project.technology,
                Project.data_context,
                Project.target_market,
                Project.location,
            ).where(Project.id == project_id)
        )
        values = row.one_or_none()
        if values is None:
            return None
        facts = await self.session.execute(
            select(ProjectFact.domain, ProjectFact.value, ProjectFact.origin, ProjectFact.status, ProjectFact.provenance, ProjectFact.uncertainty)
            .where(ProjectFact.project_id == project_id, ProjectFact.status.in_(["confirmed", "corrected"]))
            .order_by(ProjectFact.created_at, ProjectFact.id)
        )
        return ProjectContextProjection(
            project_type=values.project_type,
            country_code=values.country_code,
            user_goal=values.user_goal,
            activity=values.activity,
            sector=values.sector,
            technology=values.technology,
            data_context=values.data_context,
            target_market=values.target_market,
            location=values.location,
            facts=tuple(ProjectFactProjection(domain=row.domain, value=row.value, origin=row.origin, status=row.status, provenance=row.provenance, uncertainty=row.uncertainty) for row in facts),
        )
