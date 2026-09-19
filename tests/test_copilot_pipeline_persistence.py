import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.ai.contracts import OrchestrationRequest
from app.modules.ai.models import AgentRun, ConversationMessage, ConversationThread
from app.modules.ai.pipeline import PipelineStageRecorder
from app.modules.ai.pipeline_types import PipelineStage
from app.modules.ai.router import get_copilot_request_status
from app.modules.ai.schemas import AgentRunRequestTrace
from app.modules.ai.services import AgentRunService, ConversationService
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember
from app.modules.projects.schemas import IdeaProjectCreate
from app.modules.projects.service import ProjectService


@pytest_asyncio.fixture
async def pipeline_session() -> AsyncSession:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable for Copilot pipeline persistence: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_pipeline_stage_summaries_persist_by_request_id(pipeline_session: AsyncSession) -> None:
    request_id = uuid.uuid4()
    service = AgentRunService(pipeline_session)
    root = await service.create_run(
        request_id=request_id, agent_name="orchestrator", capability="orchestration",
        request_payload=AgentRunRequestTrace(intent="regulatory"),
    )
    await service.start_run(root.id)
    recorder = PipelineStageRecorder(service, OrchestrationRequest(request_id=request_id, intent_hint="regulatory"), parent_run_id=root.id)
    await recorder.start(PipelineStage.RETRIEVING_EVIDENCE)
    await recorder.succeed(PipelineStage.RETRIEVING_EVIDENCE, {"retrieved_chunk_count": 3})
    await recorder.start(PipelineStage.ASSESSING_EVIDENCE)
    await recorder.succeed(PipelineStage.ASSESSING_EVIDENCE, {"evidence_status": "PARTIAL", "missing_domains": "AI"})
    await recorder.start(PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE)
    await recorder.succeed(PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE, {
        "fallback_attempted": True, "fallback_domains": "AI", "fallback_evidence_count": 2,
        "fallback_unique_evidence_count": 1, "final_evidence_count": 4,
    })
    await recorder.start(PipelineStage.REASSESSING_EVIDENCE)
    await recorder.succeed(PipelineStage.REASSESSING_EVIDENCE, {
        "evidence_status": "SUFFICIENT", "final_evidence_status": "SUFFICIENT",
        "final_covered_domains": "PRIVACY, AI", "final_missing_domains": "",
    })
    await recorder.start(PipelineStage.GENERATING)
    await recorder.fail(PipelineStage.GENERATING, error_code="PROVIDER_RATE_LIMIT", error_message="safe provider failure")

    trace = await service.get_request_trace(request_id)
    assert {run.capability for run in trace} >= {
        "orchestration", "retrieving_evidence", "assessing_evidence",
        "retrieving_missing_domain_evidence", "reassessing_evidence", "generating",
    }
    generation = next(run for run in trace if run.capability == "generating")
    assessment = next(run for run in trace if run.capability == "assessing_evidence")
    assert generation.status == "failed" and generation.error_code == "PROVIDER_RATE_LIMIT"
    assert assessment.response_payload["result"]["evidence_status"] == "PARTIAL"
    fallback = next(run for run in trace if run.capability == "retrieving_missing_domain_evidence")
    assert fallback.response_payload["result"] == {
        "fallback_attempted": True, "fallback_domains": "AI", "fallback_evidence_count": 2,
        "fallback_unique_evidence_count": 1, "final_evidence_count": 4,
    }
    assert all(run.request_id == request_id for run in trace)

    await pipeline_session.execute(delete(AgentRun).where(AgentRun.request_id == request_id))
    await pipeline_session.commit()


def _actor(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=("entrepreneur",), provider="pipeline-test")


@pytest.mark.asyncio
async def test_status_endpoint_authorizes_conversation_and_active_membership(pipeline_session: AsyncSession) -> None:
    owner_id, other_id = uuid.uuid4(), uuid.uuid4()
    owner, other = _actor(owner_id, f"pipeline-owner-{owner_id}@example.test"), _actor(other_id, f"pipeline-other-{other_id}@example.test")
    request_id = uuid.uuid4()
    project_id = thread_id = None
    try:
        pipeline_session.add_all([User(id=owner_id, email=owner.email), User(id=other_id, email=other.email)])
        await pipeline_session.commit()
        project = await ProjectService(pipeline_session).create_idea(owner, IdeaProjectCreate(display_name="Pipeline status project"))
        project_id = project.id
        thread = await ConversationService(pipeline_session).create_thread(owner, title="Pipeline status", subject_type="project", subject_id=project.id)
        thread_id = thread.id
        message = await ConversationService(pipeline_session).add_user_message(owner, thread.id, "Question de test")
        runs = AgentRunService(pipeline_session)
        root = await runs.create_run(request_id=request_id, agent_name="orchestrator", capability="orchestration", user_id=owner_id, message_id=message.id, subject_type="project", subject_id=project.id, request_payload=AgentRunRequestTrace(intent="regulatory"))
        await runs.start_run(root.id)
        recorder = PipelineStageRecorder(runs, OrchestrationRequest(request_id=request_id, conversation_id=thread.id, message_id=message.id, principal=owner, subject_type="project", subject_id=project.id, intent_hint="regulatory"), parent_run_id=root.id)
        await recorder.start(PipelineStage.CONTEXT_BUILDING)
        await recorder.succeed(PipelineStage.CONTEXT_BUILDING)
        await recorder.start(PipelineStage.RETRIEVING_EVIDENCE)
        await recorder.succeed(PipelineStage.RETRIEVING_EVIDENCE, {"retrieved_chunk_count": 1})
        await recorder.start(PipelineStage.ASSESSING_EVIDENCE)
        await recorder.succeed(PipelineStage.ASSESSING_EVIDENCE, {
            "evidence_status": "SUFFICIENT",
            "required_domains": "PRIVACY",
            "covered_domains": "PRIVACY",
            "resolution_source": "QUESTION_EXPLICIT",
            "matched_signals": "question:rgpd",
            "needs_clarification": False,
        })

        own = await get_copilot_request_status(thread.id, request_id, owner, pipeline_session)
        assert own.status == "running" and own.current_stage == PipelineStage.ASSESSING_EVIDENCE
        assert own.diagnostics is not None
        assert own.diagnostics.resolution_source == "QUESTION_EXPLICIT"
        assert own.diagnostics.matched_signals == ["question:rgpd"]
        await recorder.start(PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE)
        await recorder.succeed(PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE, {
            "fallback_attempted": True, "fallback_domains": "AI", "fallback_evidence_count": 2,
            "fallback_unique_evidence_count": 1, "final_evidence_count": 2,
        })
        await recorder.start(PipelineStage.REASSESSING_EVIDENCE)
        await recorder.succeed(PipelineStage.REASSESSING_EVIDENCE, {
            "evidence_status": "SUFFICIENT", "final_evidence_status": "SUFFICIENT",
            "final_covered_domains": "PRIVACY, AI", "final_missing_domains": "",
        })
        await recorder.start(PipelineStage.RETRIEVING_AUTHORITATIVE_EVIDENCE)
        await recorder.succeed(PipelineStage.RETRIEVING_AUTHORITATIVE_EVIDENCE, {
            "authoritative_fallback_attempted": True,
            "authoritative_fallback_domains": "AI",
            "authoritative_sources_attempted": "eur_lex, european_commission_digital",
            "authoritative_sources_succeeded": "eur_lex",
            "authoritative_sources_failed": "european_commission_digital",
            "authoritative_failure_count": 1,
            "authoritative_external_evidence_count": 1,
            "authoritative_status_before": "PARTIAL",
            "authoritative_status_after": "SUFFICIENT",
        })
        await recorder.start(PipelineStage.REASSESSING_AUTHORITATIVE_EVIDENCE)
        await recorder.succeed(PipelineStage.REASSESSING_AUTHORITATIVE_EVIDENCE, {
            "evidence_status": "SUFFICIENT", "final_evidence_status": "SUFFICIENT",
            "final_covered_domains": "PRIVACY, AI", "final_missing_domains": "",
            "final_scope_supported": True,
            "authoritative_status_before": "PARTIAL",
            "authoritative_status_after": "SUFFICIENT",
        })
        await recorder.start(PipelineStage.VERIFYING)
        await recorder.fail(PipelineStage.VERIFYING, error_code="VERIFICATION_FAILED", error_message="safe verification failure", result={
            "verification_verdict": "block", "verification_reason": "bounded safe reason",
            "semantic_claim_count": 0, "supported_claim_count": 0,
            "unsupported_claim_count": 0, "unverified_claim_count": 0,
        })
        recovered = await get_copilot_request_status(thread.id, request_id, owner, pipeline_session)
        assert recovered.current_stage == PipelineStage.FAILED
        assert recovered.evidence_status.value == "SUFFICIENT"
        assert recovered.diagnostics is not None
        assert recovered.diagnostics.fallback_attempted is True
        assert recovered.diagnostics.fallback_domains == ["AI"]
        assert recovered.diagnostics.authoritative_fallback_attempted is True
        assert recovered.diagnostics.authoritative_sources_attempted == ["eur_lex", "european_commission_digital"]
        assert recovered.diagnostics.authoritative_sources_succeeded == ["eur_lex"]
        assert recovered.diagnostics.authoritative_sources_failed == ["european_commission_digital"]
        assert recovered.diagnostics.authoritative_status_after.value == "SUFFICIENT"
        assert recovered.diagnostics.final_covered_domains == ["PRIVACY", "AI"]
        assert recovered.diagnostics.verification_reason == "bounded safe reason"
        assert recovered.diagnostics.semantic_claim_count == 0
        with pytest.raises(HTTPException) as cross_user:
            await get_copilot_request_status(thread.id, request_id, other, pipeline_session)
        assert cross_user.value.status_code == 404
        with pytest.raises(HTTPException) as unknown:
            await get_copilot_request_status(thread.id, uuid.uuid4(), owner, pipeline_session)
        assert unknown.value.status_code == 404
        membership = await pipeline_session.get(ProjectMember, {"project_id": project.id, "user_id": owner_id})
        membership.status = "revoked"
        await pipeline_session.commit()
        with pytest.raises(HTTPException) as revoked:
            await get_copilot_request_status(thread.id, request_id, owner, pipeline_session)
        assert revoked.value.status_code == 404
    finally:
        if project_id is not None:
            await pipeline_session.execute(delete(AgentRun).where(AgentRun.subject_id == project_id))
        if thread_id is not None:
            await pipeline_session.execute(delete(ConversationMessage).where(ConversationMessage.thread_id == thread_id))
            await pipeline_session.execute(delete(ConversationThread).where(ConversationThread.id == thread_id))
        if project_id is not None:
            await pipeline_session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
            await pipeline_session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
            await pipeline_session.execute(delete(Project).where(Project.id == project_id))
        await pipeline_session.execute(delete(User).where(User.id.in_([owner_id, other_id])))
        await pipeline_session.commit()
