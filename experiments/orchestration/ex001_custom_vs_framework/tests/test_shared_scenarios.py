from __future__ import annotations

import json

import pytest

from ..common.evaluation import build_orchestrator


@pytest.mark.parametrize("variant", ["lightweight", "langgraph"])
@pytest.mark.parametrize("scenario_id", ["S1", "S2", "S3", "S4", "S5"])
@pytest.mark.asyncio
async def test_shared_scenarios(variant, scenario_id):
    fixture, orchestrator, trace = build_orchestrator(variant, scenario_id)
    result = await orchestrator.run(fixture.request)
    runs = trace.for_request(fixture.request.request_id)

    assert result.request_id == fixture.request.request_id
    assert all(item.model_dump() for item in result.results)
    if scenario_id == "S1":
        assert result.status == "succeeded" and len(result.results) == 1
    elif scenario_id == "S2":
        assert result.status == "succeeded" and {item.capability for item in result.results} == {"regulatory", "contract"}
    elif scenario_id == "S3":
        assert result.status == "partial"
        assert len(result.results) == 2 and "contract:controlled_failure" in result.failures
    elif scenario_id == "S4":
        assert result.status == "unauthorized"
        assert fixture.context_builder.repository.loaded_body_ids == []
        assert sum(agent.invocations.total() for agent in fixture.agents.values()) == 0
        assert "SENTINEL-FORBIDDEN-CONTENT" not in json.dumps([run.model_dump() for run in runs], default=str)
    elif scenario_id == "S5":
        assert len(runs) == 3
        assert len({run.id for run in runs}) == 3
        root = next(run for run in runs if run.parent_run_id is None)
        children = [run for run in runs if run.parent_run_id == root.id]
        assert len(children) == 2
        assert {run.request_id for run in runs} == {fixture.request.request_id}
    assert all(run.request_id == fixture.request.request_id for run in runs)


@pytest.mark.asyncio
async def test_router_and_registry_fail_closed():
    from ..common.contracts import ExperimentRequest, Intent
    from ..common.router import AgentRegistry, DeterministicRouter
    import uuid

    assert DeterministicRouter().route(Intent(capabilities=[])) == []
    with pytest.raises(ValueError):
        DeterministicRouter().route(Intent(capabilities=["future"] ))
    with pytest.raises(ValueError):
        AgentRegistry({}).resolve("unknown")
    assert ExperimentRequest(request_id=uuid.uuid4(), user_id=uuid.uuid4(), resource_id=uuid.uuid4(), scenario_id="S6", declared_intent="unsupported")

