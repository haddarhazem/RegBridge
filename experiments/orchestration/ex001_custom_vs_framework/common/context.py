from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .contracts import AuthorizedContext, ExperimentRequest


@dataclass
class FixtureResourceRepository:
    resources: dict[uuid.UUID, dict[str, str]]
    requested_ids: list[uuid.UUID] = field(default_factory=list)
    loaded_body_ids: list[uuid.UUID] = field(default_factory=list)

    def get_metadata(self, resource_id: uuid.UUID) -> dict[str, str] | None:
        self.requested_ids.append(resource_id)
        resource = self.resources.get(resource_id)
        return {"project_name": resource["project_name"]} if resource else None

    def load_authorized_projection(self, resource_id: uuid.UUID) -> AuthorizedContext:
        resource = self.resources[resource_id]
        self.loaded_body_ids.append(resource_id)
        return AuthorizedContext(
            resource_id=resource_id,
            project_name=resource["project_name"],
            authorized_summary=resource["summary"],
        )


@dataclass(frozen=True)
class FixtureAuthorizationPolicy:
    active_members: dict[uuid.UUID, set[uuid.UUID]]

    def can_view(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        return user_id in self.active_members.get(resource_id, set())


class AuthorizedContextBuilder:
    def __init__(self, policy: FixtureAuthorizationPolicy, repository: FixtureResourceRepository) -> None:
        self.policy = policy
        self.repository = repository

    def build(self, request: ExperimentRequest) -> AuthorizedContext:
        # The policy check deliberately precedes loading the sensitive projection.
        if not self.policy.can_view(request.user_id, request.resource_id):
            raise PermissionError("Resource access denied")
        if self.repository.get_metadata(request.resource_id) is None:
            raise PermissionError("Resource access denied")
        return self.repository.load_authorized_projection(request.resource_id)

