from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.exc import SQLAlchemyError

import app.db.models  # noqa: F401 - load the complete SQLAlchemy metadata registry for standalone execution

from app.modules.ai.agents import AgentRegistry
from app.modules.ai.context import AuthorizedContextBuilder
from app.modules.ai.contracts import AgentRequest, AgentResult, AuthorizedContext, OrchestrationRequest
from app.modules.ai.models import AgentRun
from app.modules.ai.orchestration import Aggregator, DeterministicIntentClassifier, Orchestrator, Router
from app.modules.ai.services import AgentRunService


class NoopContextBuilder:
    async def build(self, request, capabilities):
        return AuthorizedContext()


class TraceAgent:
    name = "trace-test-agent"
    capabilities = ("regulatory",)

    async def run(self, request: AgentRequest) -> AgentResult:
        return AgentResult(agent_name=self.name, capability=request.capability, status="succeeded", findings=["trace-safe"])


@pytest.fixture
async def trace_session() -> AsyncSession:
    database_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://regbridge:regbridge@127.0.0.1:55432/regbridge")
    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.connect():
            pass
    except (OSError, SQLAlchemyError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable for SCRUM-182 integration evidence: {exc}")
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_production_orchestrator_persists_scrum182_root_child_trace(trace_session: AsyncSession):
    request_id = uuid.uuid4()
    trace = AgentRunService(trace_session)
    orchestrator = Orchestrator(
        classifier=DeterministicIntentClassifier(),
        router=Router(AgentRegistry([TraceAgent()])),
        context_builder=NoopContextBuilder(),  # type: ignore[arg-type]
        agent_run_service=trace,
        aggregator=Aggregator(),
    )

    result = await orchestrator.run(OrchestrationRequest(request_id=request_id, intent_hint="regulatory"))
    runs = await trace.get_request_trace(request_id)

    assert result.status == "succeeded"
    assert len(runs) == 2
    root = next(run for run in runs if run.parent_run_id is None)
    child = next(run for run in runs if run.parent_run_id == root.id)
    assert root.request_id == child.request_id == request_id
    assert root.id != child.id
    assert root.status == "succeeded"
    assert child.status == "succeeded"
    assert "trace-safe" not in str(root.request_payload)
    await trace_session.execute(delete(AgentRun).where(AgentRun.request_id == request_id))
    await trace_session.commit()
