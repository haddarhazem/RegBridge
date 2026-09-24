import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.session import get_session
from app.modules.ai.copilot import ProjectCopilotService
from app.modules.ai.llm import LLMConfigurationError
from app.modules.ai.schemas import CopilotDiagnosticsResponse, CopilotRequestStatusResponse, CopilotStageResponse, CopilotTurnResponse, ConversationCreate, ConversationResponse, MessageCreate, MessageResponse
from app.modules.ai.services import ConversationService
from app.modules.ai.pipeline_types import EvidenceStatus, PipelineStage
from app.core.config import get_settings
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.core.request_id import get_request_id
from app.modules.regulatory.orchestration import build_contract_orchestrator, build_regulatory_orchestrator
from app.modules.regulatory.retrieval import RegulatoryConfigurationError, RegulatoryRetrievalError

router = APIRouter(prefix="/conversations", tags=["conversations"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


def _message_response(message) -> MessageResponse:
    return MessageResponse.model_validate(message)


def _conversation_response(thread) -> ConversationResponse:
    messages = [_message_response(message) for message in thread.__dict__.get("messages", [])]
    return ConversationResponse(
        id=thread.id, user_id=thread.user_id, title=thread.title,
        subject_type=thread.subject_type, subject_id=thread.subject_id,
        status=thread.status, created_at=thread.created_at, updated_at=thread.updated_at,
        archived_at=thread.archived_at, messages=messages,
    )


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(data: ConversationCreate, principal: Principal, session: Session) -> ConversationResponse:
    thread = await ConversationService(session).create_thread(principal, title=data.title, subject_type=data.subject_type, subject_id=data.subject_id)
    # New threads have no messages. Do not assign an unloaded relationship:
    # SQLAlchemy would lazy-load it outside an awaited async operation.
    return _conversation_response(thread)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    principal: Principal,
    session: Session,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
) -> list[ConversationResponse]:
    return [
        _conversation_response(thread)
        for thread in await ConversationService(session).list_threads(
            principal,
            subject_type=subject_type,
            subject_id=subject_id,
        )
    ]


@router.get("/{thread_id}", response_model=ConversationResponse)
async def get_conversation(thread_id: uuid.UUID, principal: Principal, session: Session) -> ConversationResponse:
    return _conversation_response(await ConversationService(session).get_thread(principal, thread_id))


@router.post("/{thread_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def add_message(thread_id: uuid.UUID, data: MessageCreate, principal: Principal, session: Session) -> MessageResponse:
    message = await ConversationService(session).add_user_message(principal, thread_id, data.content)
    return _message_response(message)


@router.post("/{thread_id}/responses", response_model=CopilotTurnResponse, status_code=status.HTTP_201_CREATED)
async def create_copilot_response(request: Request, thread_id: uuid.UUID, data: MessageCreate, principal: Principal, session: Session) -> CopilotTurnResponse:
    try:
        # A selected document always routes to the local Contract Agent. Do not
        # cold-start BGE, Qdrant, or an LLM provider for an analysis-backed
        # contract question that cannot use those capabilities.
        builder = build_contract_orchestrator if data.document_id is not None else build_regulatory_orchestrator
        orchestrator = await run_in_threadpool(builder, session)
    except (RegulatoryConfigurationError, RegulatoryRetrievalError, LLMConfigurationError):
        raise HTTPException(status_code=503, detail="Copilot is not configured") from None
    turn = await ProjectCopilotService(ConversationService(session), orchestrator).respond(
        principal,
        thread_id,
        data.content,
        document_id=data.document_id,
        document_version_id=data.document_version_id,
        analysis_id=data.analysis_id,
        request_id=get_request_id(request),
    )
    return CopilotTurnResponse(
        conversation_id=thread_id,
        user_message=_message_response(turn.user_message),
        assistant_message=_message_response(turn.assistant_message),
        orchestration_status=turn.orchestration_status,
        sources=turn.sources,
        references=turn.references,
        warnings=turn.warnings,
        candidate_extraction_attempted=turn.candidate_extraction_attempted,
        candidate_count=turn.candidate_count,
        candidate_types=turn.candidate_types or [],
        candidate_extraction_failed=turn.candidate_extraction_failed,
    )


def _stage_payload(run, stage: PipelineStage) -> dict:
    payload = run.response_payload or {}
    return payload.get("result", {}) if isinstance(payload, dict) else {}


@router.get("/{thread_id}/requests/{request_id}/status", response_model=CopilotRequestStatusResponse)
async def get_copilot_request_status(thread_id: uuid.UUID, request_id: uuid.UUID, principal: Principal, session: Session) -> CopilotRequestStatusResponse:
    """Return safe progress only after conversation and active-membership authorization."""
    thread = await ConversationService(session).get_thread(principal, thread_id)
    message_ids = {message.id for message in thread.messages}
    from app.modules.ai.services import AgentRunService
    runs = await AgentRunService(session).get_request_trace(request_id)
    runs = [run for run in runs if run.user_id == principal.user_id and run.message_id in message_ids and run.subject_type == thread.subject_type and run.subject_id == thread.subject_id]
    if not runs:
        raise HTTPException(status_code=404, detail="Copilot request not found")
    stage_runs = {run.capability.upper(): run for run in runs if run.agent_name == "copilot-pipeline"}
    ordered = [
        PipelineStage.CONTEXT_BUILDING,
        PipelineStage.RETRIEVING_EVIDENCE,
        PipelineStage.ASSESSING_EVIDENCE,
        PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE,
        PipelineStage.REASSESSING_EVIDENCE,
        PipelineStage.RETRIEVING_AUTHORITATIVE_EVIDENCE,
        PipelineStage.REASSESSING_AUTHORITATIVE_EVIDENCE,
        PipelineStage.GENERATING,
        PipelineStage.VERIFYING,
    ]
    stages: list[CopilotStageResponse] = []
    for stage in ordered:
        run = stage_runs.get(stage.value)
        if run is None:
            stages.append(CopilotStageResponse(stage=stage, status="not_started"))
            continue
        duration = ((run.completed_at or run.started_at) - run.started_at).total_seconds() * 1000
        stages.append(CopilotStageResponse(stage=stage, status=run.status, duration_ms=round(max(duration, 0), 3)))
    failed = next((stage for stage in ordered if (run := stage_runs.get(stage.value)) is not None and run.status == "failed"), None)
    completed = stage_runs.get(PipelineStage.COMPLETED.value)
    cancelled = any(run.status == "cancelled" for run in stage_runs.values())
    running_stage = next((stage for stage in reversed(ordered) if stage_runs.get(stage.value) is not None and stage_runs[stage.value].status == "running"), None)
    latest_started_stage = next((stage for stage in reversed(ordered) if stage_runs.get(stage.value) is not None), PipelineStage.CONTEXT_BUILDING)
    current = PipelineStage.CANCELLED if cancelled else PipelineStage.FAILED if failed else PipelineStage.COMPLETED if completed else running_stage or latest_started_stage
    status_value = "cancelled" if cancelled else "failed" if failed else "completed" if completed else "running"
    assessment = _stage_payload(stage_runs.get(PipelineStage.ASSESSING_EVIDENCE), PipelineStage.ASSESSING_EVIDENCE) if stage_runs.get(PipelineStage.ASSESSING_EVIDENCE) else {}
    fallback = _stage_payload(stage_runs.get(PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE), PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE) if stage_runs.get(PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE) else {}
    reassessment = _stage_payload(stage_runs.get(PipelineStage.REASSESSING_EVIDENCE), PipelineStage.REASSESSING_EVIDENCE) if stage_runs.get(PipelineStage.REASSESSING_EVIDENCE) else {}
    authoritative = _stage_payload(stage_runs.get(PipelineStage.RETRIEVING_AUTHORITATIVE_EVIDENCE), PipelineStage.RETRIEVING_AUTHORITATIVE_EVIDENCE) if stage_runs.get(PipelineStage.RETRIEVING_AUTHORITATIVE_EVIDENCE) else {}
    authoritative_reassessment = _stage_payload(stage_runs.get(PipelineStage.REASSESSING_AUTHORITATIVE_EVIDENCE), PipelineStage.REASSESSING_AUTHORITATIVE_EVIDENCE) if stage_runs.get(PipelineStage.REASSESSING_AUTHORITATIVE_EVIDENCE) else {}
    final_assessment = authoritative_reassessment or reassessment or fallback or assessment
    evidence_status = final_assessment.get("final_evidence_status") or final_assessment.get("evidence_status")
    try:
        evidence_value = EvidenceStatus(evidence_status) if evidence_status else None
    except ValueError:
        evidence_value = None
    failed_run = stage_runs.get(failed.value) if failed else None
    started = min(run.started_at for run in runs)
    completed_at = completed.completed_at if completed else (failed_run.completed_at if failed_run else None)
    diagnostics = None
    if get_settings().copilot_developer_diagnostics_enabled:
        retrieval = _stage_payload(stage_runs.get(PipelineStage.RETRIEVING_EVIDENCE), PipelineStage.RETRIEVING_EVIDENCE) if stage_runs.get(PipelineStage.RETRIEVING_EVIDENCE) else {}
        generating = _stage_payload(stage_runs.get(PipelineStage.GENERATING), PipelineStage.GENERATING) if stage_runs.get(PipelineStage.GENERATING) else {}
        verifying = _stage_payload(stage_runs.get(PipelineStage.VERIFYING), PipelineStage.VERIFYING) if stage_runs.get(PipelineStage.VERIFYING) else {}
        diagnostics = CopilotDiagnosticsResponse(
            required_domains=[item for item in str(assessment.get("required_domains") or "").split(", ") if item],
            covered_domains=[item for item in str(final_assessment.get("final_covered_domains") or final_assessment.get("covered_domains") or "").split(", ") if item],
            missing_domains=[item for item in str(final_assessment.get("final_missing_domains") or final_assessment.get("missing_domains") or "").split(", ") if item],
            retrieved_chunk_count=retrieval.get("retrieved_chunk_count"), provider=generating.get("provider"), model=generating.get("model"),
            verification_verdict=verifying.get("verification_verdict"), failure_code=failed_run.error_code if failed_run else None,
            verification_reason=verifying.get("verification_reason"),
            semantic_claim_count=verifying.get("semantic_claim_count"),
            supported_claim_count=verifying.get("supported_claim_count"),
            unsupported_claim_count=verifying.get("unsupported_claim_count"),
            unverified_claim_count=verifying.get("unverified_claim_count"),
            resolution_source=assessment.get("resolution_source"),
            matched_signals=[item for item in str(assessment.get("matched_signals") or "").split(", ") if item],
            needs_clarification=bool(assessment.get("needs_clarification")),
            question_scope=final_assessment.get("final_question_scope") or final_assessment.get("question_scope") or assessment.get("question_scope"),
            scope_signals=[item for item in str(assessment.get("scope_signals") or "").split(", ") if item],
            scope_supported=final_assessment.get("final_scope_supported") if "final_scope_supported" in final_assessment else final_assessment.get("scope_supported"),
            scope_support_reason=final_assessment.get("final_scope_support_reason") or final_assessment.get("scope_support_reason") or assessment.get("scope_support_reason"),
            initial_evidence_count=assessment.get("initial_evidence_count"),
            initial_evidence_status=assessment.get("initial_evidence_status") or assessment.get("evidence_status"),
            initial_covered_domains=[item for item in str(assessment.get("initial_covered_domains") or assessment.get("covered_domains") or "").split(", ") if item],
            initial_missing_domains=[item for item in str(assessment.get("initial_missing_domains") or assessment.get("missing_domains") or "").split(", ") if item],
            initial_question_scope=fallback.get("initial_question_scope") or assessment.get("initial_question_scope") or assessment.get("question_scope"),
            initial_scope_supported=fallback.get("initial_scope_supported") if "initial_scope_supported" in fallback else assessment.get("initial_scope_supported", assessment.get("scope_supported")),
            initial_scope_support_reason=fallback.get("initial_scope_support_reason") or assessment.get("initial_scope_support_reason") or assessment.get("scope_support_reason"),
            fallback_attempted=bool(fallback.get("fallback_attempted")),
            fallback_domains=[item for item in str(fallback.get("fallback_domains") or "").split(", ") if item],
            fallback_evidence_count=fallback.get("fallback_evidence_count"),
            fallback_unique_evidence_count=fallback.get("fallback_unique_evidence_count"),
            fallback_failed_domains=[item for item in str(fallback.get("fallback_failed_domains") or "").split(", ") if item],
            fallback_failure_count=fallback.get("fallback_failure_count"),
            authoritative_fallback_attempted=bool(authoritative.get("authoritative_fallback_attempted")),
            authoritative_fallback_domains=[item for item in str(authoritative.get("authoritative_fallback_domains") or "").split(", ") if item],
            authoritative_sources_attempted=[item for item in str(authoritative.get("authoritative_sources_attempted") or "").split(", ") if item],
            authoritative_sources_succeeded=[item for item in str(authoritative.get("authoritative_sources_succeeded") or "").split(", ") if item],
            authoritative_sources_failed=[item for item in str(authoritative.get("authoritative_sources_failed") or "").split(", ") if item],
            authoritative_failure_count=authoritative.get("authoritative_failure_count"),
            authoritative_external_evidence_count=authoritative.get("authoritative_external_evidence_count"),
            authoritative_external_unique_evidence_count=authoritative.get("authoritative_external_unique_evidence_count"),
            authoritative_final_evidence_count=authoritative.get("authoritative_final_evidence_count"),
            authoritative_status_before=authoritative.get("authoritative_status_before"),
            authoritative_status_after=authoritative.get("authoritative_status_after"),
            authoritative_scope_supported_before=authoritative.get("authoritative_scope_supported_before"),
            authoritative_scope_supported_after=authoritative.get("authoritative_scope_supported_after"),
            final_evidence_count=authoritative.get("authoritative_final_evidence_count") or final_assessment.get("final_evidence_count") or fallback.get("final_evidence_count") or assessment.get("initial_evidence_count"),
            final_evidence_status=final_assessment.get("final_evidence_status") or final_assessment.get("evidence_status"),
            final_covered_domains=[item for item in str(final_assessment.get("final_covered_domains") or final_assessment.get("covered_domains") or "").split(", ") if item],
            final_missing_domains=[item for item in str(final_assessment.get("final_missing_domains") or final_assessment.get("missing_domains") or "").split(", ") if item],
            final_question_scope=final_assessment.get("final_question_scope") or final_assessment.get("question_scope") or assessment.get("question_scope"),
            final_scope_supported=final_assessment.get("final_scope_supported") if "final_scope_supported" in final_assessment else final_assessment.get("scope_supported"),
            final_scope_support_reason=final_assessment.get("final_scope_support_reason") or final_assessment.get("scope_support_reason") or assessment.get("scope_support_reason"),
        )
    return CopilotRequestStatusResponse(
        request_id=request_id, status=status_value, current_stage=current, evidence_status=evidence_value,
        started_at=started, updated_at=max((run.completed_at or run.started_at) for run in runs), completed_at=completed_at,
        failure_stage=failed, failure_code=failed_run.error_code if failed_run else None, stages=stages, diagnostics=diagnostics,
    )
