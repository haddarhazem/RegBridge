from __future__ import annotations

import uuid
from dataclasses import dataclass

from .context import FixtureAuthorizationPolicy, FixtureResourceRepository, AuthorizedContextBuilder
from .contracts import ExperimentRequest
from .fake_agents import ContractFakeAgent, RegulatoryFakeAgent
from .router import AgentRegistry


@dataclass
class ScenarioFixture:
    request: ExperimentRequest
    context_builder: AuthorizedContextBuilder
    registry: AgentRegistry
    agents: dict[str, object]


def make_scenario(scenario_id: str) -> ScenarioFixture:
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    project_a, project_b = uuid.uuid4(), uuid.uuid4()
    resources = {
        project_a: {"project_name": "Project A", "summary": "authorized summary"},
        project_b: {"project_name": "Project B", "summary": "SENTINEL-FORBIDDEN-CONTENT"},
    }
    if scenario_id == "S4":
        user, resource, intent = user_a, project_b, "regulatory"
        members = {project_a: {user_a}}
    elif scenario_id == "S3":
        user, resource, intent = user_a, project_a, "regulatory_and_contract"
        members = {project_a: {user_a}}
    else:
        user, resource, intent = user_a, project_a, "regulatory_and_contract" if scenario_id in {"S2", "S5"} else "regulatory"
        members = {project_a: {user_a}, project_b: {user_b}}
    agents = {"regulatory": RegulatoryFakeAgent(), "contract": ContractFakeAgent({"contract"} if scenario_id == "S3" else set())}
    return ScenarioFixture(
        request=ExperimentRequest(request_id=uuid.uuid4(), user_id=user, resource_id=resource, scenario_id=scenario_id, declared_intent=intent),
        context_builder=AuthorizedContextBuilder(FixtureAuthorizationPolicy(members), FixtureResourceRepository(resources)),
        registry=AgentRegistry(agents), agents=agents,
    )

