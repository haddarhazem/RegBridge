import json
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.main import app
from app.modules.ai.models import AgentRun, ConversationMessage, ConversationThread
from app.modules.ai.schemas import AgentRunRequestTrace
from app.modules.ai.services import AgentRunService, ConversationService
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal


@pytest_asyncio.fixture
async def evidence_session() -> AsyncSession:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for SCRUM-182 evidence tests: {exc}")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="evidence-test")


@pytest.mark.asyncio
async def test_scrum182_evidence_correlation_idor_anonymous_and_secret_minimization(evidence_session: AsyncSession) -> None:
    session = evidence_session
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    email_a = f"scrum182-a-{user_a_id}@example.test"
    email_b = f"scrum182-b-{user_b_id}@example.test"
    request_id = uuid.uuid4()
    run_ids: list[uuid.UUID] = []
    thread_id: uuid.UUID | None = None

    session.add_all([User(id=user_a_id, email=email_a), User(id=user_b_id, email=email_b)])
    await session.commit()

    try:
        conversation = ConversationService(session)
        thread = await conversation.create_thread(principal(user_a_id, email_a), title="User A private thread")
        thread_id = thread.id

        with pytest.raises(Exception) as user_b_read:
            await conversation.get_thread(principal(user_b_id, email_b), thread_id)
        assert getattr(user_b_read.value, "status_code", None) == 404
        await session.rollback()

        with pytest.raises(Exception) as user_b_write:
            await conversation.add_user_message(principal(user_b_id, email_b), thread_id, "should not persist")
        assert getattr(user_b_write.value, "status_code", None) == 404
        await session.rollback()

        message_count_before = await session.scalar(select(func.count()).select_from(ConversationMessage).where(ConversationMessage.thread_id == thread_id))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            anonymous_response = await client.post("/conversations", json={"title": "anonymous attempt"})
        assert anonymous_response.status_code == 401
        message_count_after = await session.scalar(select(func.count()).select_from(ConversationMessage).where(ConversationMessage.thread_id == thread_id))
        thread_count = await session.scalar(select(func.count()).select_from(ConversationThread).where(ConversationThread.user_id == user_a_id))
        assert message_count_before == message_count_after == 0
        assert thread_count == 1

        runs = AgentRunService(session)
        root = await runs.create_run(request_id=request_id, agent_name="test-orchestrator", capability="test", request_payload=AgentRunRequestTrace(intent="root"))
        child_a = await runs.create_run(request_id=request_id, parent_run_id=root.id, agent_name="test-agent-a", capability="test", request_payload=AgentRunRequestTrace(intent="child-a"))
        child_b = await runs.create_run(request_id=request_id, parent_run_id=root.id, agent_name="test-agent-b", capability="test", request_payload=AgentRunRequestTrace(intent="child-b"))
        run_ids.extend([root.id, child_a.id, child_b.id])

        trace = await runs.get_request_trace(request_id)
        assert len(trace) == 3
        assert {run.id for run in trace} == {root.id, child_a.id, child_b.id}
        assert {run.request_id for run in trace} == {request_id}
        assert {run.parent_run_id for run in trace} == {None, root.id}
        print(f"request_id={request_id} run_ids={[str(run.id) for run in trace]} parent_ids={[str(run.parent_run_id) if run.parent_run_id else None for run in trace]}")

        unsafe_error_run = await runs.create_run(request_id=request_id, agent_name="test-agent", capability="test", request_payload=AgentRunRequestTrace(intent="failure"))
        run_ids.append(unsafe_error_run.id)
        await runs.start_run(unsafe_error_run.id)
        failed = await runs.fail_run(
            unsafe_error_run.id,
            error_code="TEST_FAILURE",
            error_message='provider response {"api_key": "SCRUM182_TEST_API_KEY_SECRET", "token": "SCRUM182_TEST_BEARER_SECRET"}',
        )

        persisted = await session.scalar(select(AgentRun).where(AgentRun.id == failed.id))
        serialized = json.dumps({"request": persisted.request_payload, "response": persisted.response_payload, "metadata": persisted.model_metadata, "error": persisted.error_message})
        assert "SCRUM182_TEST_API_KEY_SECRET" not in serialized
        assert "SCRUM182_TEST_BEARER_SECRET" not in serialized
        print("user_b_access=denied anonymous_threads_created=0 anonymous_messages_created=0 sentinels_persisted=0")
    finally:
        await session.rollback()
        await session.execute(delete(AgentRun).where(AgentRun.id.in_(run_ids)))
        if thread_id is not None:
            await session.execute(delete(ConversationThread).where(ConversationThread.id == thread_id))
        await session.execute(delete(User).where(User.id.in_([user_a_id, user_b_id])))
        await session.commit()
