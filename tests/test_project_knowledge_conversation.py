"""V1.2 safety tests for conversation-derived project knowledge."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from time import perf_counter

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.ai.context import AuthorizedContextBuilder, ProjectAuthorizationService
from app.modules.ai.copilot import ProjectCopilotService
from app.modules.ai.contracts import OrchestrationRequest
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.knowledge_enrichment import ConversationKnowledgeCandidateExtractor
from app.modules.projects.knowledge_graph import (
    GraphContextProvider,
    KnowledgeNodeType,
    KnowledgeRelation,
    ProjectKnowledgeGraphBuilder,
)
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.projects.repositories import ProjectContextRepository
from app.modules.projects.service import ProjectService


def _candidate(message: str):
    marker = uuid.uuid4()
    return ConversationKnowledgeCandidateExtractor().extract(
        project_id=marker, conversation_id=marker, message_id=marker, content=message
    )


def test_conversation_extraction_is_strict_generic_and_pending_only() -> None:
    expected = {
        "We use PostgreSQL.": ("technology", "PostgreSQL", "ADD"),
        "We chose OVHcloud for hosting.": ("provider", "OVHcloud", "ADD"),
        "We process health data.": ("data", "health data", "ADD"),
        "We are now targeting Spain.": ("market", "Spain", "ADD"),
        "We no longer use AWS.": ("technology", "AWS", "REMOVE"),
    }
    for message, (domain, value, operation) in expected.items():
        candidates = _candidate(message)
        assert len(candidates) == 1
        candidate = candidates[0]
        assert (candidate.domain, candidate.value, candidate.operation, candidate.status) == (domain, value, operation, "PENDING")
        payload = candidate.as_project_fact_payload()
        assert payload["status"] == "pending_confirmation"
        assert payload["provenance"]["source"] == "COPILOT_CONVERSATION"
        assert payload["provenance"]["message_id"]

    for message in (
        "What if we used AWS?",
        "Should we use PostgreSQL?",
        "Explain OVHcloud.",
        "Maybe we could enter Germany someday.",
        "RegBridge says we probably use AI.",
        "We sell B2B software.",
        "We plan to expand to the EU.",
    ):
        assert _candidate(message) == []


def test_provider_enters_graph_only_after_confirmation_and_is_question_targeted() -> None:
    candidate = _candidate("We chose OVHcloud for hosting.")[0]
    from app.modules.projects.knowledge_graph import GraphFactProjection, ProjectKnowledgeGraphProjection

    projection = ProjectKnowledgeGraphProjection(
        project_id=uuid.uuid4(), display_name="Generic project", project_type="idea", country_code="FR",
        activity=None, sector=None, technology=None, data_context=None, target_market=None, location=None,
        confirmed_fields=frozenset(),
    )
    builder = ProjectKnowledgeGraphBuilder()
    pending = builder.build(replace(projection, facts=(GraphFactProjection("provider", candidate.value, "pending_confirmation", "inferred"),)))
    confirmed = builder.build(replace(projection, facts=(GraphFactProjection("provider", candidate.value, "confirmed", "inferred"),)))
    assert candidate.value not in {node.label for node in pending.nodes}
    assert candidate.value in {node.label for node in confirmed.nodes}
    assert any(edge.relation == KnowledgeRelation.USES_PROVIDER for edge in confirmed.edges)
    context = GraphContextProvider().select(confirmed, "Quel fournisseur cloud utilise mon projet ?")
    assert any(node.type == KnowledgeNodeType.PROVIDER and node.label == candidate.value for node in context.nodes)


@pytest_asyncio.fixture
async def db_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable for V1.2 persistence tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def _principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=("entrepreneur",), provider="v12-test")


@pytest.mark.asyncio
async def test_conversation_candidate_persists_deduplicates_evolves_graph_and_fails_closed(db_factory: async_sessionmaker[AsyncSession]) -> None:
    owner_id, other_id, project_id, other_project_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    owner, other = _principal(owner_id, f"v12-owner-{owner_id}@example.test"), _principal(other_id, f"v12-other-{other_id}@example.test")
    conversation_id, message_id = uuid.uuid4(), uuid.uuid4()
    try:
        async with db_factory() as session:
            session.add_all([User(id=owner_id, email=owner.email), User(id=other_id, email=other.email)])
            session.add(Project(id=project_id, owner_user_id=owner_id, project_type="idea", raw_description="generic", confirmed_fields={}))
            session.add(Project(id=other_project_id, owner_user_id=owner_id, project_type="idea", raw_description="other", confirmed_fields={}))
            session.add(ProjectMember(project_id=project_id, user_id=owner_id, member_role="owner", status="active"))
            session.add(ProjectMember(project_id=other_project_id, user_id=owner_id, member_role="owner", status="active"))
            await session.commit()

        async with db_factory() as session:
            service = ProjectService(session)
            persistence_started = perf_counter()
            pending = await service.capture_conversation_knowledge_candidates(owner, project_id, conversation_id, message_id, "We chose OVHcloud for hosting.")
            assert perf_counter() - persistence_started < 1
            assert len(pending) == 1 and pending[0].status == "pending_confirmation"
            assert pending[0].provenance["conversation_id"] == str(conversation_id)
            assert await service.capture_conversation_knowledge_candidates(owner, project_id, conversation_id, message_id, "We chose OVHcloud for hosting.") == []
            candidate_id = pending[0].id
            with pytest.raises(HTTPException) as wrong_project:
                await service.confirm_fact(owner, other_project_id, candidate_id)
            assert wrong_project.value.status_code == 404
            with pytest.raises(HTTPException) as denied:
                await service.confirm_fact(other, project_id, candidate_id)
            assert denied.value.status_code == 403

        async with db_factory() as session:
            repository = ProjectContextRepository(session)
            before = await repository.load_knowledge_graph_projection(project_id)
            assert before is not None
            assert "OVHcloud" not in {node.label for node in ProjectKnowledgeGraphBuilder().build(before).nodes}
            isolated = await repository.load_knowledge_graph_projection(other_project_id)
            assert isolated is not None
            assert "OVHcloud" not in {node.label for node in ProjectKnowledgeGraphBuilder().build(isolated).nodes}
            corrected = await ProjectService(session).correct_fact(owner, project_id, candidate_id, "OVHcloud")
            assert corrected.status == "pending_confirmation"
            confirmed = await ProjectService(session).confirm_fact(owner, project_id, candidate_id)
            assert confirmed.status == "confirmed"

        async with db_factory() as session:
            repository = ProjectContextRepository(session)
            after = await repository.load_knowledge_graph_projection(project_id)
            assert after is not None
            graph = ProjectKnowledgeGraphBuilder().build(after)
            assert "OVHcloud" in {node.label for node in graph.nodes}
            context = await AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository)).build(
                OrchestrationRequest(
                    principal=owner, subject_type="project", subject_id=project_id,
                    question="Quel fournisseur cloud utilise mon projet ?", intent_hint="regulatory",
                ), ["regulatory"]
            )
            assert context.graph_context is not None
            assert any(node.type == KnowledgeNodeType.PROVIDER and node.label == "OVHcloud" for node in context.graph_context.nodes)
            duplicate = await ProjectService(session).capture_conversation_knowledge_candidates(owner, project_id, conversation_id, uuid.uuid4(), "We chose OVHcloud for hosting.")
            assert duplicate == []
            removal = await ProjectService(session).capture_conversation_knowledge_candidates(
                owner, project_id, conversation_id, uuid.uuid4(), "We no longer use OVHcloud."
            )
            assert removal[0].domain == "provider"
            assert removal[0].provenance["operation"] == "REMOVE"
            removed = await ProjectService(session).confirm_fact(owner, project_id, removal[0].id)
            assert removed.status == "deleted"
            reloaded = await repository.load_knowledge_graph_projection(project_id)
            assert reloaded is not None
            assert "OVHcloud" not in {node.label for node in ProjectKnowledgeGraphBuilder().build(reloaded).nodes}
            session.add(ProjectFact(
                project_id=project_id, domain="market", value="France", origin="user_declared", status="confirmed",
                provenance={"source_field": "market", "excerpt": "France"}, uncertainty="low",
            ))
            await session.commit()
            conflicting = await ProjectService(session).capture_conversation_knowledge_candidates(
                owner, project_id, conversation_id, uuid.uuid4(), "We are now targeting Spain."
            )
            assert conflicting[0].status == "pending_confirmation"
            assert conflicting[0].provenance["conflict_requires_clarification"] is True
    finally:
        async with db_factory() as session:
            project_ids = [project_id, other_project_id]
            await session.execute(delete(AuditLog).where(AuditLog.project_id.in_(project_ids)))
            await session.execute(delete(ProjectFact).where(ProjectFact.project_id.in_(project_ids)))
            await session.execute(delete(ProjectMember).where(ProjectMember.project_id.in_(project_ids)))
            await session.execute(delete(Project).where(Project.id.in_(project_ids)))
            await session.execute(delete(User).where(User.id.in_([owner_id, other_id])))
            await session.commit()


@dataclass
class _Message:
    id: uuid.UUID
    content: str


class _ConversationService:
    session = None

    def __init__(self, project_id: uuid.UUID) -> None:
        self.thread = type("Thread", (), {"id": uuid.uuid4(), "subject_type": "project", "subject_id": project_id})()
        self.internal: _Message | None = None
        self.payload = None

    async def get_thread(self, _actor, _thread_id):
        return self.thread

    async def add_user_message(self, _actor, _thread_id, content):
        return _Message(uuid.uuid4(), content)

    async def add_internal_message(self, _thread_id, **kwargs):
        self.payload = kwargs["content_json"]
        self.internal = _Message(uuid.uuid4(), kwargs["content"])
        return self.internal


class _Orchestrator:
    async def run(self, _request):
        result = type("Result", (), {"structured_payload": {"verification_verdict": "pass"}, "answer": "Réponse disponible.", "sources": [], "warnings": []})()
        return type("Outcome", (), {"status": "succeeded", "results": [result], "failures": [], "root_run_id": None, "pipeline_active": False})()

    async def complete_copilot_turn(self, *_args, **_kwargs):
        return None


@pytest.mark.asyncio
async def test_candidate_capture_failure_never_hides_a_successful_copilot_answer() -> None:
    actor = _principal(uuid.uuid4(), "v12-answer@example.test")
    conversations = _ConversationService(uuid.uuid4())

    class FailingCaptureCopilot(ProjectCopilotService):
        async def _capture_candidates(self, *_args, **_kwargs):
            raise RuntimeError("local candidate extraction failure")

    service = FailingCaptureCopilot(conversations, _Orchestrator())
    turn = await service.respond(actor, conversations.thread.id, "We use PostgreSQL.")
    assert turn.assistant_message.content == "Réponse disponible."
    assert turn.candidate_extraction_failed is True
    assert conversations.payload["candidate_count"] == 0
    assert conversations.payload["candidate_extraction_failed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer_source", "question", "answer"),
    [
        ("PROJECT_GRAPH", "Quel est le secteur de ce projet?", "Le secteur confirmé de votre projet est : EnergyTech."),
        ("GENERAL_EXPLANATION", "C'est quoi un B2B?", "B2B signifie Business-to-Business."),
    ],
)
async def test_non_regulatory_answer_does_not_receive_a_regulatory_verification_warning(answer_source, question, answer) -> None:
    actor = _principal(uuid.uuid4(), "v12-graph-answer@example.test")
    conversations = _ConversationService(uuid.uuid4())

    class ProjectGraphOrchestrator:
        async def run(self, _request):
            result = type("Result", (), {
                "structured_payload": {"answer_source": answer_source},
                "answer": answer,
                "sources": [],
                "warnings": ["Réponse fondée sur une information confirmée du projet, et non sur une source réglementaire."],
            })()
            return type("Outcome", (), {"status": "succeeded", "results": [result], "failures": [], "root_run_id": None, "pipeline_active": False})()

        async def complete_copilot_turn(self, *_args, **_kwargs):
            return None

    turn = await ProjectCopilotService(conversations, ProjectGraphOrchestrator()).respond(
        actor, conversations.thread.id, question
    )

    assert turn.warnings == ["Réponse fondée sur une information confirmée du projet, et non sur une source réglementaire."]
    assert "Certains éléments n’ont pas pu être vérifiés avec une fiabilité suffisante." not in conversations.payload["warnings"]
