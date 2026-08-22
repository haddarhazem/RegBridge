"""Authorized, minimized context construction for orchestration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException, status

from app.modules.ai.contracts import AuthorizedContext, OrchestrationRequest
from app.modules.identity.schemas import AuthenticatedPrincipal


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


class ProjectContextRepository(Protocol):
    async def has_active_membership(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    async def load_minimal_projection(self, project_id: uuid.UUID) -> ProjectContextProjection | None: ...


class ProjectAuthorizationService:
    """Current-membership authorization boundary for project context."""

    def __init__(self, repository: ProjectContextRepository) -> None:
        self.repository = repository

    async def require_active_member(self, principal: AuthenticatedPrincipal | None, project_id: uuid.UUID) -> None:
        if principal is None or not await self.repository.has_active_membership(project_id, principal.user_id):
            raise ContextAuthorizationError("Project context access denied")


class AuthorizedContextBuilder:
    def __init__(self, repository: ProjectContextRepository, authorization: ProjectAuthorizationService) -> None:
        self.repository = repository
        self.authorization = authorization

    async def build(self, request: OrchestrationRequest, capabilities: list[str]) -> AuthorizedContext:
        if request.subject_type is None:
            return AuthorizedContext()
        if request.subject_type != "project" or request.subject_id is None:
            raise ContextAuthorizationError("Unsupported context subject")
        await self.authorization.require_active_member(request.principal, request.subject_id)
        projection = await self.repository.load_minimal_projection(request.subject_id)
        if projection is None:
            raise ContextAuthorizationError("Project context access denied")
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
        )


def as_http_authorization_error(error: ContextAuthorizationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
