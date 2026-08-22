"""Public regulatory question endpoint using the SCRUM-183 orchestrator."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.ai.agents import AgentRegistry
from app.modules.ai.context import AuthorizedContextBuilder, ProjectAuthorizationService
from app.modules.ai.orchestration import DeterministicIntentClassifier, Orchestrator, Router
from app.modules.ai.services import AgentRunService
from app.modules.ai.llm import LLMConfigurationError
from app.modules.identity.dependencies import get_optional_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.repositories import ProjectContextRepository
from app.modules.regulatory.agent import RegulatoryAgent
from app.modules.regulatory.contracts import RegulatoryPublicResponse, RegulatoryQuestion
from app.modules.regulatory.retrieval import RegulatoryConfigurationError, RegulatoryRetrievalError, get_regulatory_retriever
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.ai.contracts import OrchestrationRequest


router = APIRouter(prefix="/regulatory", tags=["regulatory"])
Session = Annotated[AsyncSession, Depends(get_session)]
OptionalPrincipal = Annotated[AuthenticatedPrincipal | None, Depends(get_optional_authenticated_principal)]


def build_regulatory_orchestrator(session: AsyncSession) -> Orchestrator:
    repository = ProjectContextRepository(session)
    return Orchestrator(
        classifier=DeterministicIntentClassifier(),
        router=Router(AgentRegistry([RegulatoryAgent(retriever=get_regulatory_retriever(), provider=get_mistral_provider())])),
        context_builder=AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository)),
        agent_run_service=AgentRunService(session),
    )


@router.post("/questions", response_model=RegulatoryPublicResponse)
async def answer_regulatory_question(data: RegulatoryQuestion, principal: OptionalPrincipal, session: Session) -> RegulatoryPublicResponse:
    if data.subject_type is not None and data.subject_type != "project":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported context subject")
    try:
        orchestrator = build_regulatory_orchestrator(session)
    except (RegulatoryConfigurationError, RegulatoryRetrievalError, LLMConfigurationError):
        raise HTTPException(status_code=503, detail="Regulatory retrieval is not configured") from None
    result = await orchestrator.run(OrchestrationRequest(
        question=data.question,
        principal=principal,
        subject_type="project" if data.subject_id is not None else None,
        subject_id=data.subject_id,
        intent_hint="regulatory",
        locale="fr",
    ))
    if result.status == "unauthorized":
        raise HTTPException(status_code=404, detail="Project context not found")
    if result.results:
        answer = result.results[0]
        if answer.structured_payload.get("verification_verdict") == "block":
            return RegulatoryPublicResponse(
                answer="La réponse générée n'a pas pu être vérifiée de manière fiable.",
                sources=[],
            )
        return RegulatoryPublicResponse(answer=answer.answer or "", sources=answer.sources)
    if result.failures and result.failures[0].error_code == "insufficient_evidence":
        return RegulatoryPublicResponse(answer="Les sources réglementaires disponibles sont insuffisantes pour répondre de manière fiable.", sources=[])
    raise HTTPException(status_code=503, detail="Regulatory answer service is temporarily unavailable")
