from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from app.modules.ai.agents import AgentRegistry
from app.modules.ai.context import AuthorizedContextBuilder, ProjectAuthorizationService, ProjectContextProjection
from app.modules.ai.contracts import AgentRequest, AgentResult, OrchestrationRequest
from app.modules.ai.orchestration import Aggregator, DeterministicIntentClassifier, Orchestrator, Router
from app.modules.identity.schemas import AuthenticatedPrincipal


@dataclass
class Run:
    id: uuid.UUID
    request_id: uuid.UUID
    parent_run_id: uuid.UUID | None
    agent_name: str
    capability: str
    status: str = "queued"


class TraceDouble:
    def __init__(self):
        self.runs: list[Run] = []

    async def create_run(self, *, request_id, parent_run_id, agent_name, capability, **kwargs):
        if parent_run_id is not None:
            assert next(run for run in self.runs if run.id == parent_run_id).request_id == request_id
        run = Run(uuid.uuid4(), request_id, parent_run_id, agent_name, capability)
        self.runs.append(run)
        return run

    async def start_run(self, run_id):
        next(run for run in self.runs if run.id == run_id).status = "running"

    async def succeed_run(self, run_id, payload):
        next(run for run in self.runs if run.id == run_id).status = "succeeded"

    async def fail_run(self, run_id, *, error_code, error_message):
        next(run for run in self.runs if run.id == run_id).status = "failed"


class CountingProjectRepository:
    def __init__(self, *, active_users: set[uuid.UUID]):
        self.active_users = active_users
        self.membership_checks = 0
        self.projection_loads = 0
        self.projection = ProjectContextProjection("startup", "FR", "build a safer product")

    async def has_active_membership(self, project_id, user_id):
        self.membership_checks += 1
        return user_id in self.active_users

    async def load_minimal_projection(self, project_id):
        self.projection_loads += 1
        return self.projection


class ControlledAgent:
    def __init__(self, name, capability, *, fail=False, raise_error=False):
        self.name = name
        self.capabilities = (capability,)
        self.fail = fail
        self.raise_error = raise_error
        self.requests: list[AgentRequest] = []

    async def run(self, request):
        self.requests.append(request)
        assert isinstance(request, AgentRequest)
        assert not hasattr(request, "session")
        assert not hasattr(request, "repository")
        if self.raise_error:
            raise RuntimeError("sentinel-agent-secret")
        return AgentResult(
            agent_name=self.name,
            capability=request.capability,
            status="failed" if self.fail else "succeeded",
            error_code="controlled_failure" if self.fail else None,
            findings=[] if self.fail else ["safe finding"],
        )


class PlainStringAgent(ControlledAgent):
    async def run(self, request):
        return "plain string"


def make_orchestrator(*, agents, repository, principal=None):
    request = OrchestrationRequest(
        request_id=uuid.uuid4(),
        principal=principal,
        subject_type="project" if principal else None,
        subject_id=uuid.uuid4() if principal else None,
        intent_hint="regulatory_and_contract" if len(agents) == 2 else "regulatory",
    )
    trace = TraceDouble()
    builder = AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository))
    orchestrator = Orchestrator(
        classifier=DeterministicIntentClassifier(),
        router=Router(AgentRegistry(agents)),
        context_builder=builder,
        agent_run_service=trace,
        aggregator=Aggregator(),
    )
    return request, orchestrator, trace


@pytest.mark.asyncio
async def test_single_and_multi_agent_trace_hierarchy():
    principal = AuthenticatedPrincipal(user_id=uuid.uuid4(), email="a@example.test", roles=(), provider="test")
    repository = CountingProjectRepository(active_users={principal.user_id})
    agents = [ControlledAgent("regulatory", "regulatory"), ControlledAgent("contract", "contract")]
    request, orchestrator, trace = make_orchestrator(agents=agents, repository=repository, principal=principal)

    result = await orchestrator.run(request)

    assert result.status == "succeeded"
    assert [item.capability for item in result.results] == ["regulatory", "contract"]
    assert repository.projection_loads == 1
    assert len(trace.runs) == 3
    root = trace.runs[0]
    assert all(run.request_id == request.request_id for run in trace.runs)
    assert all(run.parent_run_id == root.id for run in trace.runs[1:])
    assert len({run.id for run in trace.runs}) == 3


@pytest.mark.asyncio
async def test_partial_and_all_failures_preserve_provenance():
    principal = AuthenticatedPrincipal(user_id=uuid.uuid4(), email="a@example.test", roles=(), provider="test")
    repository = CountingProjectRepository(active_users={principal.user_id})
    agents = [ControlledAgent("regulatory", "regulatory"), ControlledAgent("contract", "contract", raise_error=True)]
    request, orchestrator, trace = make_orchestrator(agents=agents, repository=repository, principal=principal)
    result = await orchestrator.run(request)
    assert result.status == "partial"
    assert [item.capability for item in result.results] == ["regulatory"]
    assert [item.capability for item in result.failures] == ["contract"]
    assert [run.status for run in trace.runs] == ["succeeded", "succeeded", "failed"]
    assert "sentinel-agent-secret" not in result.model_dump_json()

    all_fail = [ControlledAgent("regulatory", "regulatory", fail=True), ControlledAgent("contract", "contract", fail=True)]
    request, orchestrator, trace = make_orchestrator(agents=all_fail, repository=repository, principal=principal)
    result = await orchestrator.run(request)
    assert result.status == "failed"
    assert len(result.failures) == 2
    assert trace.runs[0].status == "succeeded"


@pytest.mark.asyncio
async def test_unauthorized_revoked_and_anonymous_context_fail_before_projection():
    user_id = uuid.uuid4()
    principal = AuthenticatedPrincipal(user_id=user_id, email="a@example.test", roles=(), provider="test")
    repository = CountingProjectRepository(active_users=set())
    agent = ControlledAgent("regulatory", "regulatory")
    request, orchestrator, trace = make_orchestrator(agents=[agent], repository=repository, principal=principal)
    result = await orchestrator.run(request)
    assert result.status == "unauthorized"
    assert repository.projection_loads == 0
    assert agent.requests == []
    assert len(trace.runs) == 1

    anonymous_request = OrchestrationRequest(request_id=uuid.uuid4(), intent_hint="regulatory", subject_type="project", subject_id=uuid.uuid4())
    result = await orchestrator.run(anonymous_request)
    assert result.status == "unauthorized"
    assert repository.projection_loads == 0


@pytest.mark.asyncio
async def test_unknown_intent_no_fallback_and_plain_string_rejected():
    repository = CountingProjectRepository(active_users=set())
    trace = TraceDouble()
    agent = ControlledAgent("regulatory", "regulatory")
    builder = AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository))
    orchestrator = Orchestrator(
        classifier=DeterministicIntentClassifier(),
        router=Router(AgentRegistry([agent])),
        context_builder=builder,
        agent_run_service=trace,
    )
    result = await orchestrator.run(OrchestrationRequest(request_id=uuid.uuid4(), intent_hint="unknown"))
    assert result.status == "unsupported"
    assert len(trace.runs) == 1
    assert agent.requests == []

    bad = PlainStringAgent("regulatory", "regulatory")
    repository.active_users = {uuid.uuid4()}
    principal = AuthenticatedPrincipal(user_id=next(iter(repository.active_users)), email="a@example.test", roles=(), provider="test")
    request = OrchestrationRequest(request_id=uuid.uuid4(), principal=principal, subject_type="project", subject_id=uuid.uuid4(), intent_hint="regulatory")
    trace = TraceDouble()
    orchestrator = Orchestrator(classifier=DeterministicIntentClassifier(), router=Router(AgentRegistry([bad])), context_builder=builder, agent_run_service=trace)
    result = await orchestrator.run(request)
    assert result.status == "failed"
    assert result.failures[0].error_code == "agent_execution_failed"


def test_registry_and_router_reject_duplicates_and_unknown_capabilities():
    first = ControlledAgent("one", "regulatory")
    with pytest.raises(ValueError):
        AgentRegistry([first, ControlledAgent("two", "regulatory")])
    registry = AgentRegistry([first])
    with pytest.raises(ValueError):
        registry.resolve("missing")

