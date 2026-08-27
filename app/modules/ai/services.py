import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import get_settings
from app.modules.ai.models import AgentRun, ConversationMessage, ConversationThread
from app.modules.ai.repositories import AgentRunRepository, ConversationRepository
from app.modules.ai.schemas import AgentRunRequestTrace, AgentRunResponseTrace, ModelTraceMetadata
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.authorization import ProjectAuthorizationPolicy
from app.modules.projects.models import Project, ProjectMember
from app.core.observability import emit_event, metrics


class ConversationService:
    def __init__(self, session: AsyncSession, policy: ProjectAuthorizationPolicy | None = None) -> None:
        self.session = session
        self.repository = ConversationRepository(session)
        self.policy = policy or ProjectAuthorizationPolicy()

    async def _authorized(self, actor: AuthenticatedPrincipal, thread: ConversationThread | None) -> ConversationThread:
        if thread is None or thread.status == "deleted" or thread.user_id != actor.user_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if thread.subject_type == "project":
            project = await self.session.scalar(select(Project).where(Project.id == thread.subject_id))
            membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == thread.subject_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
            if project is None or membership is None or membership.status != "active":
                raise HTTPException(status_code=404, detail="Conversation not found")
        elif thread.subject_type is not None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return thread

    async def create_thread(self, actor: AuthenticatedPrincipal, *, title: str | None = None, subject_type: str | None = None, subject_id: uuid.UUID | None = None) -> ConversationThread:
        if subject_type == "project":
            project = await self.session.scalar(select(Project).where(Project.id == subject_id))
            membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == subject_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
            if project is None or membership is None or membership.status != "active":
                raise HTTPException(status_code=404, detail="Project not found")
        elif subject_type is not None:
            raise HTTPException(status_code=404, detail="Unsupported conversation subject")
        thread = await self.repository.create_thread(user_id=actor.user_id, title=title, subject_type=subject_type, subject_id=subject_id)
        await self.session.commit()
        return thread

    async def list_threads(self, actor: AuthenticatedPrincipal) -> list[ConversationThread]:
        threads = await self.repository.list_threads_for_user(actor.user_id)
        authorized: list[ConversationThread] = []
        for thread in threads:
            try:
                authorized.append(await self._authorized(actor, thread))
            except HTTPException:
                continue
        return authorized

    async def get_thread(self, actor: AuthenticatedPrincipal, thread_id: uuid.UUID) -> ConversationThread:
        thread = await self._authorized(actor, await self.repository.get_thread_by_id(thread_id))
        set_committed_value(thread, "messages", await self.repository.list_messages(thread.id))
        return thread

    async def add_user_message(self, actor: AuthenticatedPrincipal, thread_id: uuid.UUID, content: str, parent_message_id: uuid.UUID | None = None) -> ConversationMessage:
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            thread = await self._authorized(actor, await self.repository.get_thread_by_id(thread_id))
            return await self.repository.add_message(thread, role="user", content=content, parent_message_id=parent_message_id)

    async def add_internal_message(self, thread_id: uuid.UUID, *, role: str, content: str, parent_message_id: uuid.UUID | None = None, status: str = "completed", content_json=None) -> ConversationMessage:
        if role not in {"assistant", "system", "tool", "user"}:
            raise ValueError("Unsupported message role")
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            thread = await self.repository.get_thread_by_id(thread_id)
            if thread is None or thread.status == "deleted":
                raise HTTPException(status_code=404, detail="Conversation not found")
            return await self.repository.add_message(thread, role=role, content=content, parent_message_id=parent_message_id, status=status, content_json=content_json)


_SENSITIVE = re.compile(
    r"(?ix)("
    r"[\"']?(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret)[\"']?"
    r"\s*[:=]\s*[\"']?(?:bearer\s+)?[^\"',}\s]+[\"']?"
    r"|bearer\s+[A-Za-z0-9._~+/=-]+"
    r"|sk-[A-Za-z0-9_-]+"
    r")"
)


def _safe_error_message(message: str, limit: int = 1000) -> str:
    sanitized = _SENSITIVE.sub("[REDACTED]", message).replace("\x00", "")
    return sanitized[:limit]


class AgentRunService:
    TERMINAL = {"succeeded", "failed", "cancelled"}
    TRANSITIONS = {"queued": {"running", "cancelled"}, "running": {"succeeded", "failed", "cancelled"}, "succeeded": set(), "failed": set(), "cancelled": set()}

    def __init__(self, session: AsyncSession, *, max_payload_bytes: int | None = None) -> None:
        self.session = session
        self.repository = AgentRunRepository(session)
        self.max_payload_bytes = max_payload_bytes or get_settings().trace_max_payload_bytes

    def _json_payload(self, value) -> dict:
        if not isinstance(value, (AgentRunRequestTrace, AgentRunResponseTrace, ModelTraceMetadata)):
            raise TypeError("Trace payloads require an explicit trace-safe Pydantic model")
        payload = value.model_dump(mode="json", exclude_none=True)
        serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        if len(serialized.encode("utf-8")) > self.max_payload_bytes:
            raise ValueError("Trace payload exceeds configured size limit")
        return payload

    async def create_run(self, *, request_id: uuid.UUID, agent_name: str, capability: str, request_payload: AgentRunRequestTrace, model_metadata: ModelTraceMetadata | None = None, parent_run_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None, message_id: uuid.UUID | None = None, subject_type: str | None = None, subject_id: uuid.UUID | None = None, prompt_version: str | None = None, status: str = "queued") -> AgentRun:
        request_json = self._json_payload(request_payload)
        model_json = self._json_payload(model_metadata or ModelTraceMetadata())
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            if parent_run_id is not None:
                parent = await self.repository.get_parent_run(parent_run_id)
                if parent is None:
                    raise ValueError("Parent run does not exist")
                if parent.request_id != request_id:
                    raise ValueError("Child run must use the parent request_id")
            if status not in {"queued", "running"}:
                raise ValueError("Runs may only be created queued or running")
            run = await self.repository.create_run(request_id=request_id, parent_run_id=parent_run_id, user_id=user_id, message_id=message_id, agent_name=agent_name, capability=capability, subject_type=subject_type, subject_id=subject_id, request_payload=request_json, model_metadata=model_json, prompt_version=prompt_version, status=status)
            metrics.increment("regbridge_agent_runs_total", component="genai", operation="create", status=status)
            emit_event("agent_run.created", component="genai", operation="create", status=status, run_id=str(run.id), parent_run_id=str(parent_run_id) if parent_run_id else None, agent_name=agent_name, capability=capability)
            return run

    async def _transition(self, run_id: uuid.UUID, target: str, *, response_payload=None, error_code: str | None = None, error_message: str | None = None) -> AgentRun:
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            run = await self.repository.get_run(run_id)
            if run is None:
                raise ValueError("Run does not exist")
            if target not in self.TRANSITIONS.get(run.status, set()):
                raise ValueError(f"Invalid run transition: {run.status} -> {target}")
            run.status = target
            if target in self.TERMINAL:
                run.completed_at = datetime.now(timezone.utc)
            if target == "succeeded" and response_payload is not None:
                run.response_payload = self._json_payload(response_payload)
            if target == "failed":
                run.error_code = error_code[:80] if error_code else "run_failed"
                run.error_message = _safe_error_message(error_message or "Agent run failed")
            await self.session.flush()
            metrics.increment("regbridge_agent_runs_total", component="genai", operation="transition", status=target)
            emit_event("agent_run.transitioned", component="genai", operation="transition", status=target, run_id=str(run.id), error_code=run.error_code)
            return run

    async def start_run(self, run_id: uuid.UUID) -> AgentRun:
        return await self._transition(run_id, "running")

    async def succeed_run(self, run_id: uuid.UUID, response_payload: AgentRunResponseTrace) -> AgentRun:
        return await self._transition(run_id, "succeeded", response_payload=response_payload)

    async def fail_run(self, run_id: uuid.UUID, *, error_code: str, error_message: str) -> AgentRun:
        return await self._transition(run_id, "failed", error_code=error_code, error_message=error_message)

    async def cancel_run(self, run_id: uuid.UUID) -> AgentRun:
        return await self._transition(run_id, "cancelled")

    async def get_request_trace(self, request_id: uuid.UUID) -> list[AgentRun]:
        return await self.repository.list_runs_by_request_id(request_id)

    async def get_run(self, run_id: uuid.UUID) -> AgentRun | None:
        return await self.repository.get_run(run_id)
