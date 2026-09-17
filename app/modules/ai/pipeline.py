"""Typed, trace-safe Copilot pipeline observability primitives.

The pipeline remains part of the modular-monolith orchestration layer.  It is
deliberately not an agent framework and stores its operational events in the
existing ``agent_runs`` hierarchy.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.core.observability import emit_event
from app.modules.ai.schemas import AgentRunRequestTrace, AgentRunResponseTrace
from app.modules.ai.pipeline_types import EvidenceStatus, PipelineStage

if TYPE_CHECKING:
    from app.modules.ai.contracts import OrchestrationRequest
    from app.modules.ai.services import AgentRunService


class PipelineStageRecorder:
    """Persist only allowlisted operational summaries for one Copilot turn."""

    def __init__(
        self,
        service: "AgentRunService",
        request: "OrchestrationRequest",
        *,
        parent_run_id: uuid.UUID,
    ) -> None:
        self.service = service
        self.request = request
        self.parent_run_id = parent_run_id
        self._runs: dict[PipelineStage, uuid.UUID] = {}

    async def start(self, stage: PipelineStage, *, parent_run_id: uuid.UUID | None = None) -> uuid.UUID:
        existing = self._runs.get(stage)
        if existing is not None:
            return existing
        run = await self.service.create_run(
            request_id=self.request.request_id,
            parent_run_id=parent_run_id or self.parent_run_id,
            user_id=self.request.principal.user_id if self.request.principal else None,
            message_id=self.request.message_id,
            agent_name="copilot-pipeline",
            capability=stage.value.lower(),
            subject_type=self.request.subject_type,
            subject_id=self.request.subject_id,
            request_payload=AgentRunRequestTrace(intent=f"copilot:{stage.value.lower()}", locale=self.request.locale),
        )
        await self.service.start_run(run.id)
        self._runs[stage] = run.id
        emit_event("copilot.stage.started", component="copilot", operation=stage.value.lower(), status="started", stage=stage.value)
        return run.id

    async def succeed(self, stage: PipelineStage, result: dict[str, str | int | float | bool | None] | None = None) -> None:
        run_id = self._runs.get(stage)
        if run_id is None:
            return
        await self.service.succeed_run(
            run_id,
            AgentRunResponseTrace(summary=f"Copilot {stage.value.lower()} completed", result=result or {}),
        )
        emit_event("copilot.stage.completed", component="copilot", operation=stage.value.lower(), status="succeeded", stage=stage.value, **(result or {}))

    async def fail(
        self,
        stage: PipelineStage,
        *,
        error_code: str,
        error_message: str,
        result: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        run_id = self._runs.get(stage)
        if run_id is None:
            return
        await self.service.fail_run(
            run_id,
            error_code=error_code,
            error_message=error_message,
            response_payload=AgentRunResponseTrace(summary=f"Copilot {stage.value.lower()} failed", result=result or {}),
        )
        emit_event("copilot.stage.failed", component="copilot", operation=stage.value.lower(), status="failed", stage=stage.value, failure_code=error_code, **(result or {}))
