import json
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.ai.agents import Agent, AgentRegistry
from app.modules.ai.context import AuthorizedContextBuilder, ProjectAuthorizationService
from app.modules.ai.contracts import AgentRequest, AgentResult, OrchestrationRequest
from app.modules.ai.llm import LLMExecutionMetadata, LLMGenerationRequest, LLMGenerationResponse
from app.modules.ai.copilot import ProjectCopilotService
from app.modules.ai.models import AgentRun, ConversationMessage, ConversationThread
from app.modules.ai.orchestration import DeterministicIntentClassifier, Orchestrator, Router
from app.modules.ai.services import AgentRunService, ConversationService
from app.modules.ai.router import create_conversation
from app.modules.ai.schemas import ConversationCreate
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.projects.repositories import ProjectContextRepository
from app.modules.projects.schemas import IdeaProjectCreate
from app.modules.projects.service import ProjectService
from app.modules.regulatory.agent import RegulatoryAgent
from app.modules.regulatory.contracts import RegulatoryEvidence


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
            answer="Contexte autorisÃ©: " + ", ".join(values),
            sources=["CNIL", "CNIL"],
            structured_payload={"verification_verdict": "pass"},
        )


class StableRegulatoryRetriever:
    async def retrieve(self, question: str) -> list[RegulatoryEvidence]:
        return [RegulatoryEvidence(
            point_id="entrepreneur-integration-point-1",
            rank=1,
            retrieval_score=0.99,
            organization="CNIL",
            source_domain="cnil.fr",
            content="Les obligations applicables dÃ©pendent du traitement de donnÃ©es dÃ©crit.",
        )]


class StableRegulatoryProvider:
    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        execution = LLMExecutionMetadata(
            provider="integration-test",
            logical_model="integration-test-model",
            model="integration-test-model",
            prompt_version=request.prompt_version,
            operation=request.operation,
            status="success",
            duration_ms=1,
        )
        if request.operation == "semantic_verification":
            content = json.dumps({
                "claims": [{
                    "claim_id": "claim-1",
                    "support": "supported",
                    "evidence_ids": ["entrepreneur-integration-point-1"],
                    "reason": "La formulation reste limitÃ©e Ã  la source fournie.",
                }],
                "verdict": "pass",
                "reasons": ["Les affirmations sont couvertes par la preuve fournie."],
            })
        else:
            content = "Les obligations dÃ©pendent du traitement de donnÃ©es dÃ©crit dans la source autorisÃ©e."
        return LLMGenerationResponse(
            content=content,
            model="integration-test-model",
            execution=execution,
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
            thread = await create_conversation(ConversationCreate(title="Project A Copilot", subject_type="project", subject_id=project_ids[0]), owner, session)
            assert thread.messages == []
            thread_id = thread.id
            repository = ProjectContextRepository(session)
            agent = ContextEchoAgent()
            request_id = uuid.uuid4()
            orchestrator = Orchestrator(
                classifier=DeterministicIntentClassifier(),
                router=Router(AgentRegistry([agent])),
                context_builder=AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository)),
                agent_run_service=AgentRunService(session),
            )
            turn = await ProjectCopilotService(conversation_service, orchestrator).respond(owner, thread.id, "Quelles obligations concernent ce projet ?", request_id=request_id)

            assert turn.sources == ["CNIL"]
            assert turn.assistant_message.parent_message_id == turn.user_message.id
            assert agent.received is not None
            assert agent.received.subject_id == project_ids[0]
            assert [item["value"] for item in agent.received.authorized_context.facts] == ["confirmed-value"]
            traces = await AgentRunService(session).get_request_trace(request_id)
            assert len(traces) == 2
            assert all(trace.request_id == request_id for trace in traces)

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


@pytest.mark.asyncio
async def test_real_regulatory_agent_path_persists_correlated_traces(
    vertical_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = uuid.uuid4()
    email = f"vertical-agent-{user_id}@example.test"
    owner = actor(user_id, email)
    project_id: uuid.UUID | None = None
    request_id: uuid.UUID | None = None

    async with vertical_factory() as session:
        session.add(User(id=user_id, email=email))
        await session.commit()

    try:
        async with vertical_factory() as session:
            project = await ProjectService(session).create_idea(
                owner,
                IdeaProjectCreate(display_name="Regulatory agent project"),
            )
            project_id = project.id
            session.add(ProjectFact(
                project_id=project.id,
                domain="activity",
                value="Traitement de donnÃ©es personnelles",
                origin="user_declared",
                status="confirmed",
                provenance={"source_field": "activity"},
                uncertainty="low",
            ))
            await session.commit()

        async with vertical_factory() as session:
            request = OrchestrationRequest(
                question="Quelles obligations principales s'appliquent Ã  ce traitement ?",
                principal=owner,
                subject_type="project",
                subject_id=project_id,
                intent_hint="regulatory",
                locale="fr",
            )
            request_id = request.request_id
            agent = RegulatoryAgent(
                retriever=StableRegulatoryRetriever(),
                provider=StableRegulatoryProvider(),
            )
            orchestrator = Orchestrator(
                classifier=DeterministicIntentClassifier(),
                router=Router(AgentRegistry([agent])),
                context_builder=AuthorizedContextBuilder(
                    ProjectContextRepository(session),
                    ProjectAuthorizationService(ProjectContextRepository(session)),
                ),
                agent_run_service=AgentRunService(session),
            )

            result = await orchestrator.run(request)

            assert result.status == "succeeded"
            assert result.selected_capabilities == ["regulatory"]
            assert len(result.results) == 1
            agent_result = result.results[0]
            assert agent_result.answer is not None
            assert "obligations" in agent_result.answer
            assert agent_result.sources == ["CNIL"]
            assert agent_result.evidence[0]["point_id"] == "entrepreneur-integration-point-1"
            assert agent_result.structured_payload["verification_verdict"] == "pass"
            assert agent_result.structured_payload["generation_provider"] == "integration-test"

            traces = await AgentRunService(session).get_request_trace(request.request_id)
            assert len(traces) == 2
            root = next(trace for trace in traces if trace.parent_run_id is None)
            child = next(trace for trace in traces if trace.parent_run_id is not None)
            assert all(trace.request_id == request.request_id for trace in traces)
            assert child.parent_run_id == root.id
            assert {trace.status for trace in traces} == {"succeeded"}
            assert child.response_payload["source_refs"][0]["source_id"] == "entrepreneur-integration-point-1"
            assert child.response_payload["result"]["verification_verdict"] == "pass"
    finally:
        async with vertical_factory() as session:
            if request_id is not None:
                await session.execute(delete(AgentRun).where(AgentRun.request_id == request_id))
            if project_id is not None:
                await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
                await session.execute(delete(ProjectFact).where(ProjectFact.project_id == project_id))
                await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
                await session.execute(delete(Project).where(Project.id == project_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
