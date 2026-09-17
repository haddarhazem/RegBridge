"""Focused project reads used by authorized AI context construction."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
                Project.confirmed_fields,
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
        fact_rows = list(facts.all())
        confirmed = values.confirmed_fields or {}
        confirmed_fact_values = {
            {"data": "data_context", "market": "target_market"}.get(row.domain, row.domain): row.value
            for row in fact_rows
            if row.status in {"confirmed", "corrected"}
        }

        def confirmed_value(field: str, value):
            if confirmed.get(field) == "confirmed":
                return value
            return confirmed_fact_values.get(field)

        return ProjectContextProjection(
            project_type=values.project_type,
            country_code=values.country_code,
            user_goal=values.user_goal,
            activity=confirmed_value("activity", values.activity),
            sector=confirmed_value("sector", values.sector),
            technology=confirmed_value("technology", values.technology),
            data_context=confirmed_value("data", values.data_context),
            target_market=confirmed_value("market", values.target_market),
            location=confirmed_value("location", values.location),
            facts=tuple(ProjectFactProjection(domain=row.domain, value=row.value, origin=row.origin, status=row.status, provenance=row.provenance, uncertainty=row.uncertainty) for row in fact_rows),
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
        assessment_version = None
        if roadmap.regulatory_assessment_id is not None:
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

    async def load_document_projection(self, project_id: uuid.UUID, user_id: uuid.UUID, document_id: uuid.UUID, version_id: uuid.UUID):
        from app.modules.documents.authorization import DocumentAuthorizationPolicy
        from app.modules.documents.extraction import extraction_status
        from app.modules.documents.models import Document, DocumentVersion
        from app.modules.ai.projections import DocumentProjection

        document = await self.session.scalar(select(Document).where(Document.id == document_id, Document.project_id == project_id, Document.deleted_at.is_(None)))
        membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id, ProjectMember.status == "active"))
        if document is None or membership is None or not DocumentAuthorizationPolicy().can_read(document.visibility, document.classification, membership, document.owner_user_id, user_id):
            return None
        version = await self.session.scalar(select(DocumentVersion).where(DocumentVersion.id == version_id, DocumentVersion.document_id == document.id, DocumentVersion.malware_scan_status == "clean"))
        if version is None or extraction_status(version) != "ready":
            return None
        return DocumentProjection(id=document.id, title=document.title, document_type=document.document_type, classification=document.classification, visibility=document.visibility, version_id=version.id, version_number=version.version_number, extracted_text=(version.extracted_text or "")[:6000] or None)

    async def load_contract_analysis_projection(self, project_id: uuid.UUID, user_id: uuid.UUID, analysis_id: uuid.UUID, document_id: uuid.UUID, version_id: uuid.UUID):
        from app.modules.ai.projections import ContractAnalysisProjection, ContractObservationProjection
        from app.modules.documents.authorization import DocumentAuthorizationPolicy
        from app.modules.documents.contract_analysis_models import ContractAnalysis
        from app.modules.documents.models import Document

        analysis = await self.session.scalar(select(ContractAnalysis).where(ContractAnalysis.id == analysis_id, ContractAnalysis.project_id == project_id, ContractAnalysis.document_id == document_id, ContractAnalysis.document_version_id == version_id).options(selectinload(ContractAnalysis.findings)))
        document = await self.session.scalar(select(Document).where(Document.id == document_id, Document.project_id == project_id, Document.deleted_at.is_(None)))
        membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id, ProjectMember.status == "active"))
        if analysis is None or document is None or membership is None or not DocumentAuthorizationPolicy().can_read(document.visibility, document.classification, membership, document.owner_user_id, user_id):
            return None
        observations = [ContractObservationProjection(id=finding.id, category=finding.category, source_quote=finding.evidence_quote, document_version_id=finding.evidence_document_version_id, start_char=finding.evidence_start_char, end_char=finding.evidence_end_char) for finding in analysis.findings[:20]]
        return ContractAnalysisProjection(id=analysis.id, document_id=analysis.document_id, document_version_id=analysis.document_version_id, strategy=analysis.strategy, status=analysis.status, observations=observations, limitations=["Les interprétations sémantiques de risque et de recommandation ne sont pas incluses."])
