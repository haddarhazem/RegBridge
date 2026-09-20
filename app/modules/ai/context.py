"""Authorized, minimized context construction for orchestration."""

from __future__ import annotations

import uuid
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException, status

from app.modules.ai.contracts import AuthorizedContext, OrchestrationRequest
from app.modules.ai.projections import AssessmentProjection, ContractAnalysisProjection, DocumentProjection, RoadmapProjection
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.knowledge_graph import GraphContextProvider, ProjectKnowledgeGraphBuilder


class ContextAuthorizationError(Exception):
    """Safe domain error for denied or unsupported context."""


@dataclass(frozen=True)
class ProjectFactProjection:
    domain: str
    value: str
    origin: str
    status: str
    provenance: dict[str, str | None]
    uncertainty: str


@dataclass(frozen=True)
class ProjectContextProjection:
    project_type: str
    country_code: str
    user_goal: str | None
    activity: str | None = None
    sector: str | None = None
    technology: str | None = None
    data_context: str | None = None
    target_market: str | None = None
    location: str | None = None
    facts: tuple[ProjectFactProjection, ...] = ()
    assessment: AssessmentProjection | None = None
    roadmap: RoadmapProjection | None = None


class ProjectContextRepository(Protocol):
    async def has_active_membership(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    async def load_minimal_projection(self, project_id: uuid.UUID) -> ProjectContextProjection | None: ...

    async def load_latest_assessment_projection(self, project_id: uuid.UUID) -> AssessmentProjection | None: ...

    async def load_latest_roadmap_projection(self, project_id: uuid.UUID) -> RoadmapProjection | None: ...

    async def load_document_projection(self, project_id: uuid.UUID, user_id: uuid.UUID, document_id: uuid.UUID, version_id: uuid.UUID) -> DocumentProjection | None: ...

    async def load_contract_analysis_projection(self, project_id: uuid.UUID, user_id: uuid.UUID, analysis_id: uuid.UUID, document_id: uuid.UUID, version_id: uuid.UUID) -> ContractAnalysisProjection | None: ...

    async def load_knowledge_graph_projection(self, project_id: uuid.UUID): ...


def _normalized_question(question: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", question.lower())
        if not unicodedata.combining(character)
    )


def requests_assessment_context(question: str) -> bool:
    normalized = _normalized_question(question)
    return any(term in normalized for term in (
        "mon evaluation", "cette obligation", "pourquoi cette obligation",
        "cette recommandation", "mon incertitude", "incertitudes",
        "explique mon evaluation", "evaluation reglementaire",
    ))


def requests_roadmap_context(question: str) -> bool:
    normalized = _normalized_question(question)
    return any(term in normalized for term in (
        "roadmap", "etape", "prochaine etape", "prochaines etapes", "etapes encore",
        "etapes a faire", "que dois-je faire ensuite", "que faire ensuite",
    ))


def requests_document_context(question: str) -> bool:
    normalized = _normalized_question(question)
    return any(term in normalized for term in (
        "document", "contrat", "nda", "clause", "passage", "constat", "extrait",
    ))


class ProjectAuthorizationService:
    """Current-membership authorization boundary for project context."""

    def __init__(self, repository: ProjectContextRepository) -> None:
        self.repository = repository

    async def require_active_member(self, principal: AuthenticatedPrincipal | None, project_id: uuid.UUID) -> None:
        if principal is None or not await self.repository.has_active_membership(project_id, principal.user_id):
            raise ContextAuthorizationError("Project context access denied")


class AuthorizedContextBuilder:
    def __init__(self, repository: ProjectContextRepository, authorization: ProjectAuthorizationService, graph_context_provider: GraphContextProvider | None = None) -> None:
        self.repository = repository
        self.authorization = authorization
        self.graph_context_provider = graph_context_provider or GraphContextProvider()

    async def build(self, request: OrchestrationRequest, capabilities: list[str]) -> AuthorizedContext:
        if request.subject_type is None:
            return AuthorizedContext()
        if request.subject_type != "project" or request.subject_id is None:
            raise ContextAuthorizationError("Unsupported context subject")
        await self.authorization.require_active_member(request.principal, request.subject_id)
        projection = await self.repository.load_minimal_projection(request.subject_id)
        if projection is None:
            raise ContextAuthorizationError("Project context access denied")
        assessment = None
        roadmap = None
        document = None
        contract_analysis = None
        graph_context = None
        if requests_assessment_context(request.question):
            loader = getattr(self.repository, "load_latest_assessment_projection", None)
            if loader is not None:
                assessment = await loader(request.subject_id)
        if requests_roadmap_context(request.question):
            loader = getattr(self.repository, "load_latest_roadmap_projection", None)
            if loader is not None:
                roadmap = await loader(request.subject_id)
        if request.context_document_id is not None and request.context_version_id is not None:
            loader = getattr(self.repository, "load_document_projection", None)
            if loader is not None:
                document = await loader(request.subject_id, request.principal.user_id, request.context_document_id, request.context_version_id)
            if document is None:
                raise ContextAuthorizationError("Document context access denied")
        if request.context_analysis_id is not None and request.context_document_id is not None and request.context_version_id is not None:
            loader = getattr(self.repository, "load_contract_analysis_projection", None)
            if loader is not None:
                contract_analysis = await loader(request.subject_id, request.principal.user_id, request.context_analysis_id, request.context_document_id, request.context_version_id)
            if contract_analysis is None:
                raise ContextAuthorizationError("Contract analysis context access denied")
        graph_loader = getattr(self.repository, "load_knowledge_graph_projection", None)
        if graph_loader is not None:
            graph_projection = await graph_loader(request.subject_id)
            if graph_projection is not None:
                graph_context = self.graph_context_provider.select(ProjectKnowledgeGraphBuilder().build(graph_projection), request.question)
        return AuthorizedContext(
            subject_type="project",
            subject_id=request.subject_id,
            project_type=projection.project_type,
            country_code=projection.country_code,
            user_goal=projection.user_goal,
            activity=projection.activity,
            sector=projection.sector,
            technology=projection.technology,
            data_context=projection.data_context,
            target_market=projection.target_market,
            location=projection.location,
            facts=[{"domain": fact.domain, "value": fact.value, "origin": fact.origin, "status": fact.status, "provenance": fact.provenance, "uncertainty": fact.uncertainty} for fact in projection.facts],
            assessment=assessment,
            roadmap=roadmap,
            document=document,
            contract_analysis=contract_analysis,
            graph_context=graph_context,
        )


def as_http_authorization_error(error: ContextAuthorizationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
