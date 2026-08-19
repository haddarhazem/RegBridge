import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import AgentRun, ConversationMessage, ConversationThread


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_thread(self, **values) -> ConversationThread:
        thread = ConversationThread(**values)
        self.session.add(thread)
        await self.session.flush()
        return thread

    async def get_thread_by_id(self, thread_id: uuid.UUID) -> ConversationThread | None:
        return await self.session.scalar(select(ConversationThread).where(ConversationThread.id == thread_id))

    async def get_owned_thread(self, thread_id: uuid.UUID, user_id: uuid.UUID) -> ConversationThread | None:
        return await self.session.scalar(select(ConversationThread).where(ConversationThread.id == thread_id, ConversationThread.user_id == user_id))

    async def list_threads_for_user(self, user_id: uuid.UUID) -> list[ConversationThread]:
        result = await self.session.scalars(
            select(ConversationThread)
            .where(ConversationThread.user_id == user_id, ConversationThread.status != "deleted")
            .order_by(ConversationThread.updated_at.desc(), ConversationThread.id.asc())
        )
        return list(result.all())

    async def add_message(self, thread: ConversationThread, *, role: str, content: str, parent_message_id: uuid.UUID | None = None, status: str = "completed", content_json=None) -> ConversationMessage:
        if parent_message_id is not None:
            parent = await self.session.scalar(select(ConversationMessage).where(ConversationMessage.id == parent_message_id))
            if parent is None or parent.thread_id != thread.id:
                raise ValueError("Parent message must belong to the same conversation thread")
        message = ConversationMessage(thread_id=thread.id, role=role, content=content, parent_message_id=parent_message_id, status=status, content_json=content_json)
        self.session.add(message)
        thread.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return message

    async def list_messages(self, thread_id: uuid.UUID) -> list[ConversationMessage]:
        result = await self.session.scalars(
            select(ConversationMessage).where(ConversationMessage.thread_id == thread_id).order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        )
        return list(result.all())

    async def update_thread_status(self, thread: ConversationThread, status: str, archived_at=None) -> ConversationThread:
        thread.status = status
        thread.archived_at = archived_at
        await self.session.flush()
        return thread


class AgentRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(self, **values) -> AgentRun:
        run = AgentRun(**values)
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(self, run_id: uuid.UUID) -> AgentRun | None:
        return await self.session.scalar(select(AgentRun).where(AgentRun.id == run_id))

    async def get_parent_run(self, run_id: uuid.UUID) -> AgentRun | None:
        return await self.get_run(run_id)

    async def list_runs_by_request_id(self, request_id: uuid.UUID) -> list[AgentRun]:
        result = await self.session.scalars(select(AgentRun).where(AgentRun.request_id == request_id).order_by(AgentRun.started_at.asc(), AgentRun.id.asc()))
        return list(result.all())

    async def list_child_runs(self, parent_run_id: uuid.UUID) -> list[AgentRun]:
        result = await self.session.scalars(select(AgentRun).where(AgentRun.parent_run_id == parent_run_id).order_by(AgentRun.started_at.asc(), AgentRun.id.asc()))
        return list(result.all())
