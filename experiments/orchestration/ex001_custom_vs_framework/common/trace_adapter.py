from __future__ import annotations

import uuid
from typing import Protocol

from app.modules.ai.schemas import AgentRunRequestTrace, AgentRunResponseTrace
from app.modules.ai.services import AgentRunService

from .contracts import AgentExecutionResult, TraceRun


class TraceAdapter(Protocol):
    async def create(self, *, request_id: uuid.UUID, agent_name: str, capability: str, parent_run_id: uuid.UUID | None) -> uuid.UUID: ...
    async def succeed(self, run_id: uuid.UUID, result: AgentExecutionResult) -> None: ...
    async def fail(self, run_id: uuid.UUID, error_code: str, message: str) -> None: ...


class InMemoryTraceAdapter:
    """Same SCRUM-182 IDs, correlation, hierarchy, and allowlisted payloads."""

    def __init__(self) -> None:
        self.runs: dict[uuid.UUID, TraceRun] = {}

    async def create(self, *, request_id, agent_name, capability, parent_run_id):
        if parent_run_id is not None and (parent_run_id not in self.runs or self.runs[parent_run_id].request_id != request_id):
            raise ValueError("Invalid trace parent")
        run_id = uuid.uuid4()
        self.runs[run_id] = TraceRun(
            id=run_id, request_id=request_id, parent_run_id=parent_run_id,
            agent_name=agent_name, capability=capability, status="running",
            request_payload=AgentRunRequestTrace(intent=capability, experiment_id="EX-001").model_dump(mode="json"),
        )
        return run_id

    async def succeed(self, run_id, result):
        run = self.runs[run_id]
        run.status = "succeeded"
        run.response_payload = AgentRunResponseTrace(summary=result.agent_name, result={"status": result.status, "capability": result.capability}).model_dump(mode="json")

    async def fail(self, run_id, error_code, message):
        run = self.runs[run_id]
        run.status = "failed"
        run.error_code = error_code

    def for_request(self, request_id):
        return [run for run in self.runs.values() if run.request_id == request_id]


class Scrum182TraceAdapter:
    """Adapter for the existing AgentRunService, with no second trace model."""

    def __init__(self, service: AgentRunService) -> None:
        self.service = service

    async def create(self, *, request_id, agent_name, capability, parent_run_id):
        run = await self.service.create_run(
            request_id=request_id,
            parent_run_id=parent_run_id,
            agent_name=agent_name,
            capability=capability,
            request_payload=AgentRunRequestTrace(intent=capability, experiment_id="EX-001", configuration_version="1"),
        )
        await self.service.start_run(run.id)
        return run.id

    async def succeed(self, run_id, result):
        await self.service.succeed_run(run_id, AgentRunResponseTrace(summary=result.agent_name, result={"status": result.status, "capability": result.capability}))

    async def fail(self, run_id, error_code, message):
        await self.service.fail_run(run_id, error_code=error_code, error_message=message)

