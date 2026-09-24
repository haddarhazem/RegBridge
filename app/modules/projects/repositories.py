"""Focused project reads used by authorized AI context construction."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.ai.context import ProjectContextProjection, ProjectFactProjection
from app.modules.ai.projections import AssessmentConclusionProjection, AssessmentProjection, RoadmapItemProjection, RoadmapProjection
from app.modules.documents.models import Document
from app.modules.projects.knowledge_graph import (
    GraphDocumentProjection,
    GraphFactProjection,
    GraphRegulatoryAssessmentProjection,
    ProjectKnowledgeGraphProjection,
)
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.projects.profile_models import StartupProfile, StartupProfileField


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

    async def load_knowledge_graph_projection(self, project_id: uuid.UUID) -> ProjectKnowledgeGraphProjection | None:
        """Load only metadata already authorized by the caller for the graph read model."""
        project = await self.session.scalar(select(Project).where(Project.id == project_id))
        if project is None:
            return None
        facts = list((await self.session.scalars(
            select(ProjectFact)
            .where(ProjectFact.project_id == project_id, ProjectFact.status.in_(["confirmed", "corrected"]))
            .order_by(ProjectFact.created_at, ProjectFact.id)
        )).all())
        documents = list((await self.session.scalars(
            select(Document)
            .where(Document.project_id == project_id, Document.deleted_at.is_(None))
            .order_by(Document.created_at, Document.id)
            .limit(20)
        )).all())
        # Only an assessment that the existing verifier accepted can enrich the
        # graph.  Its sources remain provenance, not legal conclusions.
        from app.modules.regulatory.assessment_models import RegulatoryAssessment
        assessment = await self.session.scalar(
            select(RegulatoryAssessment)
            .where(
                RegulatoryAssessment.project_id == project_id,
                RegulatoryAssessment.status == "completed",
                RegulatoryAssessment.verification_verdict.in_(("pass", "pass_with_warnings")),
            )
            .order_by(RegulatoryAssessment.version.desc())
            .limit(1)
        )
        regulatory_assessment = None
        if assessment is not None:
            result = assessment.result or {}
            raw_domains = result.get("regulatory_domains") or result.get("domains") or []
            domains = tuple(
                value.strip() for value in raw_domains[:12]
                if isinstance(value, str) and value.strip() and len(value.strip()) <= 120
            ) if isinstance(raw_domains, list) else ()
            organizations = tuple(dict.fromkeys(
                str(item.get("organization")).strip()
                for item in (assessment.source_provenance or [])[:20]
                if isinstance(item, dict) and isinstance(item.get("organization"), str) and item["organization"].strip()
            ))
            regulatory_assessment = GraphRegulatoryAssessmentProjection(
                id=assessment.id,
                version=assessment.version,
                verification_verdict=assessment.verification_verdict,
                domains=domains,
                evidence_organizations=organizations,
            )
        confirmed = {field for field, value in (project.confirmed_fields or {}).items() if value == "confirmed"}
        # ``business_model`` is a structured startup-profile field.  This
        # projection is only reached after active project-member authorization,
        # matching the internal profile read boundary.
        business_model = await self.session.scalar(
            select(StartupProfileField.value)
            .join(StartupProfile, StartupProfile.id == StartupProfileField.profile_id)
            .where(
                StartupProfile.project_id == project_id,
                StartupProfileField.field_name == "business_model",
            )
        )
        return ProjectKnowledgeGraphProjection(
            project_id=project.id,
            display_name=project.display_name,
            project_type=project.project_type,
            country_code=project.country_code,
            activity=project.activity,
            sector=project.sector,
            technology=project.technology,
            data_context=project.data_context,
            target_market=project.target_market,
            location=project.location,
            confirmed_fields=frozenset(confirmed),
            business_model=business_model if isinstance(business_model, str) else None,
            facts=tuple(GraphFactProjection(
                domain=fact.domain,
                value=fact.value,
                status=fact.status,
                origin=fact.origin,
                id=fact.id,
                provenance={key: value for key, value in (fact.provenance or {}).items() if isinstance(value, str) and key in {"source_field", "source_locator", "rule", "extraction_method"}},
            ) for fact in facts),
            documents=tuple(GraphDocumentProjection(
                id=document.id,
                title=document.title,
                document_type=document.document_type,
                classification=document.classification,
                visibility=document.visibility,
            ) for document in documents),
            regulatory_assessment=regulatory_assessment,
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
        from app.modules.ai.projections import ContractAnalysisProjection, ContractClauseProjection
        from app.modules.documents.authorization import DocumentAuthorizationPolicy
        from app.modules.documents.contract_analysis_models import ContractAnalysis
        from app.modules.documents.models import Document, DocumentVersion

        analysis = await self.session.scalar(select(ContractAnalysis).where(ContractAnalysis.id == analysis_id, ContractAnalysis.project_id == project_id, ContractAnalysis.document_version_id == version_id).options(selectinload(ContractAnalysis.clauses)))
        document = await self.session.scalar(select(Document).where(Document.id == document_id, Document.project_id == project_id, Document.deleted_at.is_(None)))
        version = await self.session.scalar(select(DocumentVersion).where(DocumentVersion.id == version_id, DocumentVersion.document_id == document_id))
        membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id, ProjectMember.status == "active"))
        if analysis is None or document is None or version is None or membership is None or not DocumentAuthorizationPolicy().can_read(document.visibility, document.classification, membership, document.owner_user_id, user_id):
            return None
        clauses = []
        for clause in analysis.clauses[:20]:
            refs = clause.source_refs if isinstance(clause.source_refs, dict) else {}
            detail = refs.get("analysis") if isinstance(refs.get("analysis"), dict) else {}
            clauses.append(ContractClauseProjection(
                id=clause.id,
                clause_type=clause.clause_type,
                title=detail.get("title") or clause.heading or clause.clause_type or "Clause analysée",
                status=detail.get("status") or "FOUND",
                risk_level=clause.risk_level,
                source_text=clause.extracted_text[:4000],
                source_location=detail.get("source_location"),
                verification_status=detail.get("verification_status") or "UNVERIFIED",
                source_method=detail.get("source_method") or "NATIVE",
                evidence_quotes=[item.get("quote", "")[:1200] for item in refs.get("evidence", []) if isinstance(item, dict) and isinstance(item.get("quote"), str)][:4],
                plain_language_summary=detail.get("plain_language_summary") or clause.finding or "Passage analysé.",
                purpose=detail.get("purpose") or "Le rôle de cette disposition doit être examiné dans son contexte.",
                issues=detail.get("issues", []),
                why_it_matters=detail.get("why_it_matters"),
                recommendation=clause.recommendation,
                suggested_revision=detail.get("suggested_revision"),
                limitations=detail.get("limitations", []),
            ))
        return ContractAnalysisProjection(
            id=analysis.id,
            document_id=document.id,
            document_version_id=analysis.document_version_id,
            status=analysis.verification_status,
            summary=analysis.summary,
            contract_type=analysis.contract_type,
            clauses=clauses,
            limitations=["Les résultats expliquent les passages détectés et ne constituent pas un avis juridique."],
        )
