import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.ai.agents import Agent, AgentRegistry
from app.modules.ai.context import AuthorizedContextBuilder, ProjectAuthorizationService
from app.modules.ai.contracts import AgentRequest, AgentResult
from app.modules.ai.copilot import ProjectCopilotService
from app.modules.ai.models import AgentRun, ConversationMessage, ConversationThread
from app.modules.ai.orchestration import DeterministicIntentClassifier, Orchestrator, Router
from app.modules.ai.services import AgentRunService, ConversationService
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.projects.repositories import ProjectContextRepository
from app.modules.projects.schemas import IdeaProjectCreate
from app.modules.projects.service import ProjectService


@pytest_asyncio.fixture
async def vertical_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for entrepreneur integration tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def actor(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=("entrepreneur",), provider="entrepreneur-integration-test")


class ContextEchoAgent(Agent):
    name = "context-echo-agent"
    capabilities = ("regulatory",)
    received: AgentRequest | None = None

    async def run(self, request: AgentRequest) -> AgentResult:
        self.received = request
        values = [str(item["value"]) for item in request.authorized_context.facts]
        return AgentResult(
            agent_name=self.name,
            capability="regulatory",
            status="succeeded",
            answer="Contexte autorisé: " + ", ".join(values),
            sources=["CNIL", "CNIL"],
            structured_payload={"verification_verdict": "pass"},
        )


@pytest.mark.asyncio
async def test_server_project_catalog_and_persisted_authorized_copilot_turn(vertical_factory: async_sessionmaker[AsyncSession]) -> None:
    owner_id, other_id = uuid.uuid4(), uuid.uuid4()
    owner_email = f"vertical-owner-{owner_id}@example.test"
    other_email = f"vertical-other-{other_id}@example.test"
    owner, other = actor(owner_id, owner_email), actor(other_id, other_email)
    project_ids: list[uuid.UUID] = []
    thread_id: uuid.UUID | None = None

    async with vertical_factory() as session:
        session.add_all([User(id=owner_id, email=owner_email), User(id=other_id, email=other_email)])
        await session.commit()

    try:
        async with vertical_factory() as session:
            project_a = await ProjectService(session).create_idea(owner, IdeaProjectCreate(display_name="Project A"))
            project_b = await ProjectService(session).create_idea(other, IdeaProjectCreate(display_name="Project B"))
            project_ids = [project_a.id, project_b.id]
            session.add(ProjectMember(project_id=project_a.id, user_id=other_id, member_role="viewer", status="invited"))
            session.add_all([
                ProjectFact(project_id=project_a.id, domain="data", value="pending-secret", origin="inferred", status="pending_confirmation", provenance={"source_field": "description"}, uncertainty="medium"),
                ProjectFact(project_id=project_a.id, domain="sector", value="confirmed-value", origin="inferred", status="confirmed", provenance={"source_field": "description"}, uncertainty="low"),
                ProjectFact(project_id=project_a.id, domain="technology", value="rejected-secret", origin="inferred", status="deleted", provenance={"source_field": "description"}, uncertainty="high"),
            ])
            await session.commit()

        async with vertical_factory() as session:
            owner_projects = await ProjectService(session).list_for_user(owner)
            other_projects = await ProjectService(session).list_for_user(other)
            assert [project.id for project, _ in owner_projects] == [project_ids[0]]
            assert [project.id for project, _ in other_projects] == [project_ids[1]]

            conversation_service = ConversationService(session)
            thread = await conversation_service.create_thread(owner, title="Project A Copilot", subject_type="project", subject_id=project_ids[0])
            thread_id = thread.id
            repository = ProjectContextRepository(session)
            agent = ContextEchoAgent()
            orchestrator = Orchestrator(
                classifier=DeterministicIntentClassifier(),
                router=Router(AgentRegistry([agent])),
                context_builder=AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository)),
                agent_run_service=AgentRunService(session),
            )
            turn = await ProjectCopilotService(conversation_service, orchestrator).respond(owner, thread.id, "Quelles obligations concernent ce projet ?")

            assert turn.sources == ["CNIL"]
            assert turn.assistant_message.parent_message_id == turn.user_message.id
            assert agent.received is not None
            assert agent.received.subject_id == project_ids[0]
            assert [item["value"] for item in agent.received.authorized_context.facts] == ["confirmed-value"]

        async with vertical_factory() as session:
            persisted = await ConversationService(session).get_thread(owner, thread_id)
            assert [message.role for message in persisted.messages] == ["user", "assistant"]
            assert persisted.messages[1].content_json["sources"] == ["CNIL"]
            with pytest.raises(HTTPException) as denied:
                await ConversationService(session).get_thread(other, thread_id)
            assert denied.value.status_code == 404
    finally:
        async with vertical_factory() as session:
            await session.execute(delete(AgentRun).where(AgentRun.subject_id.in_(project_ids)))
            if thread_id is not None:
                await session.execute(delete(ConversationMessage).where(ConversationMessage.thread_id == thread_id))
                await session.execute(delete(ConversationThread).where(ConversationThread.id == thread_id))
            await session.execute(delete(AuditLog).where(AuditLog.project_id.in_(project_ids)))
            await session.execute(delete(ProjectFact).where(ProjectFact.project_id.in_(project_ids)))
            await session.execute(delete(ProjectMember).where(ProjectMember.project_id.in_(project_ids)))
            await session.execute(delete(Project).where(Project.id.in_(project_ids)))
            await session.execute(delete(User).where(User.id.in_([owner_id, other_id])))
            await session.commit()
