"""Focused project reads used by authorized AI context construction."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.context import ProjectContextProjection, ProjectFactProjection
from app.modules.ai.projections import AssessmentConclusionProjection, AssessmentProjection, RoadmapItemProjection, RoadmapProjection
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

    async def load_latest_assessment_projection(self, project_id: uuid.UUID) -> AssessmentProjection | None:
        from app.modules.regulatory.assessment_models import RegulatoryAssessment

        assessment = await self.session.scalar(
            select(RegulatoryAssessment)
            .where(
                RegulatoryAssessment.project_id == project_id,
                RegulatoryAssessment.status == "completed",
                or_(RegulatoryAssessment.verification_verdict.is_(None), RegulatoryAssessment.verification_verdict != "block"),
            )
            .order_by(RegulatoryAssessment.version.desc())
            .limit(1)
        )
        if assessment is None:
            return None
        result = assessment.result or {}
        try:
            return AssessmentProjection(
                id=assessment.id,
                version=assessment.version,
                snapshot_id=assessment.snapshot_id,
                status=assessment.status,
                obligations=[AssessmentConclusionProjection.model_validate(item) for item in result.get("obligations", [])[:20]],
                recommendations=[AssessmentConclusionProjection.model_validate(item) for item in result.get("recommendations", [])[:20]],
                uncertainties=[AssessmentConclusionProjection.model_validate(item) for item in result.get("uncertainties", [])[:20]],
                sources=[str(item) for item in result.get("sources", [])[:10]],
            )
        except Exception:
            return None

    async def load_latest_roadmap_projection(self, project_id: uuid.UUID) -> RoadmapProjection | None:
        from app.modules.regulatory.assessment_models import RegulatoryAssessment
        from app.modules.regulatory.roadmap_models import LaunchRoadmap, LaunchRoadmapItem

        roadmap = await self.session.scalar(
            select(LaunchRoadmap)
            .where(LaunchRoadmap.project_id == project_id, LaunchRoadmap.status == "active")
            .order_by(LaunchRoadmap.version.desc())
            .limit(1)
        )
        if roadmap is None:
            return None
        assessment_version = await self.session.scalar(
            select(RegulatoryAssessment.version).where(
                RegulatoryAssessment.id == roadmap.regulatory_assessment_id,
                RegulatoryAssessment.project_id == project_id,
            )
        )
        if assessment_version is None:
            return None
        rows = await self.session.scalars(
            select(LaunchRoadmapItem)
            .where(LaunchRoadmapItem.roadmap_id == roadmap.id)
            .order_by(LaunchRoadmapItem.priority_order, LaunchRoadmapItem.id)
            .limit(20)
        )
        try:
            items = [RoadmapItemProjection.model_validate({
                "id": item.id,
                "item_type": item.item_type,
                "title": item.title,
                "priority_order": item.priority_order,
                "status": item.status,
                "justification": item.justification,
                "source_conclusion_refs": item.source_conclusion_refs or [],
            }) for item in rows]
            return RoadmapProjection(
                id=roadmap.id,
                version=roadmap.version,
                status=roadmap.status,
                regulatory_assessment_id=roadmap.regulatory_assessment_id,
                assessment_version=assessment_version,
                items=items,
            )
        except Exception:
            return None
