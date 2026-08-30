import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.ai.copilot import ProjectCopilotService
from app.modules.ai.llm import LLMConfigurationError
from app.modules.ai.schemas import CopilotTurnResponse, ConversationCreate, ConversationResponse, MessageCreate, MessageResponse
from app.modules.ai.services import ConversationService
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.regulatory.orchestration import build_regulatory_orchestrator
from app.modules.regulatory.retrieval import RegulatoryConfigurationError, RegulatoryRetrievalError

router = APIRouter(prefix="/conversations", tags=["conversations"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


def _message_response(message) -> MessageResponse:
    return MessageResponse.model_validate(message)


def _conversation_response(thread) -> ConversationResponse:
    messages = [_message_response(message) for message in thread.__dict__.get("messages", [])]
    return ConversationResponse.model_validate({**thread.__dict__, "messages": messages})


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(data: ConversationCreate, principal: Principal, session: Session) -> ConversationResponse:
    thread = await ConversationService(session).create_thread(principal, title=data.title, subject_type=data.subject_type, subject_id=data.subject_id)
    thread.messages = []
    return _conversation_response(thread)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(principal: Principal, session: Session) -> list[ConversationResponse]:
    return [_conversation_response(thread) for thread in await ConversationService(session).list_threads(principal)]


@router.get("/{thread_id}", response_model=ConversationResponse)
async def get_conversation(thread_id: uuid.UUID, principal: Principal, session: Session) -> ConversationResponse:
    return _conversation_response(await ConversationService(session).get_thread(principal, thread_id))


@router.post("/{thread_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def add_message(thread_id: uuid.UUID, data: MessageCreate, principal: Principal, session: Session) -> MessageResponse:
    message = await ConversationService(session).add_user_message(principal, thread_id, data.content)
    return _message_response(message)


@router.post("/{thread_id}/responses", response_model=CopilotTurnResponse, status_code=status.HTTP_201_CREATED)
async def create_copilot_response(thread_id: uuid.UUID, data: MessageCreate, principal: Principal, session: Session) -> CopilotTurnResponse:
    try:
        orchestrator = build_regulatory_orchestrator(session)
    except (RegulatoryConfigurationError, RegulatoryRetrievalError, LLMConfigurationError):
        raise HTTPException(status_code=503, detail="Copilot is not configured") from None
    turn = await ProjectCopilotService(ConversationService(session), orchestrator).respond(principal, thread_id, data.content)
    return CopilotTurnResponse(
        conversation_id=thread_id,
        user_message=_message_response(turn.user_message),
        assistant_message=_message_response(turn.assistant_message),
        orchestration_status=turn.orchestration_status,
        sources=turn.sources,
        references=turn.references,
        warnings=turn.warnings,
    )
