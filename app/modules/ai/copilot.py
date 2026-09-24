"""Authenticated project Copilot over the approved production orchestrator."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.modules.ai.contracts import OrchestrationRequest
from app.modules.ai.orchestration import Orchestrator
from app.modules.ai.services import ConversationService
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.service import ProjectService


def _copilot_intent(content: str, *, document_id: uuid.UUID | None, analysis_id: uuid.UUID | None) -> str:
    """Keep contract questions within their selected document-analysis scope.

    A compliance question about an analysed contract is deliberately routed to
    the Contract Agent for a qualified response rather than executing two
    unrelated agents and accidentally publishing only one of their answers.
    """
    normalized = content.casefold()
    regulatory_markers = ("rgpd", "ai act", "réglementation", "reglementation", "cnil", "obligation légale", "obligation legale")
    contract_markers = ("contrat", "clause", "résiliation", "resiliation", "confidential", "propriété intellectuelle", "propriete intellectuelle", "responsabilité", "responsabilite", "pénalité", "penalite", "non-concurrence", "non concurrence", "signer")
    if analysis_id is not None or document_id is not None or any(marker in normalized for marker in contract_markers):
        return "contract"
    if any(marker in normalized for marker in regulatory_markers):
        return "regulatory"
    return "regulatory"


@dataclass(frozen=True)
class CopilotTurn:
    user_message: object
    assistant_message: object
    orchestration_status: str
    sources: list[str]
    references: list[str]
    warnings: list[str]
    candidate_extraction_attempted: bool = False
    candidate_count: int = 0
    candidate_types: list[str] | None = None
    candidate_extraction_failed: bool = False


class ProjectCopilotService:
    def __init__(self, conversation_service: ConversationService, orchestrator: Orchestrator) -> None:
        self.conversations = conversation_service
        self.orchestrator = orchestrator

    async def _capture_candidates(
        self,
        actor: AuthenticatedPrincipal,
        *,
        project_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        content: str,
    ):
        """Small override seam for focused failure-isolation tests."""
        return await ProjectService(self.conversations.session).capture_conversation_knowledge_candidates(
            actor, project_id, conversation_id, message_id, content
        )

    async def respond(
        self,
        actor: AuthenticatedPrincipal,
        thread_id: uuid.UUID,
        content: str,
        document_id: uuid.UUID | None = None,
        document_version_id: uuid.UUID | None = None,
        analysis_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
    ) -> CopilotTurn:
        thread = await self.conversations.get_thread(actor, thread_id)
        if thread.subject_type != "project" or thread.subject_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A project-scoped conversation is required",
            )

        user_message = await self.conversations.add_user_message(actor, thread.id, content)
        orchestration_request = OrchestrationRequest(
            request_id=request_id or uuid.uuid4(),
            conversation_id=thread.id,
            message_id=user_message.id,
            question=content,
            principal=actor,
            subject_type="project",
            subject_id=thread.subject_id,
            context_document_id=document_id,
            context_version_id=document_version_id,
            context_analysis_id=analysis_id,
            intent_hint=_copilot_intent(content, document_id=document_id, analysis_id=analysis_id),
            locale="fr",
        )
        outcome = await self.orchestrator.run(orchestration_request)
        if outcome.status == "unauthorized":
            raise HTTPException(status_code=404, detail="Project context not found")

        sources: list[str] = []
        references: list[str] = []
        if outcome.results:
            result = outcome.results[0]
            if result.structured_payload.get("verification_verdict") == "block":
                answer = "La réponse générée n’a pas pu être vérifiée de manière fiable."
            else:
                answer = result.answer or "Aucune réponse fiable n’est disponible."
                sources = list(dict.fromkeys(result.sources))
                assessment_version = result.structured_payload.get("assessment_version")
                roadmap_version = result.structured_payload.get("roadmap_version")
                if isinstance(assessment_version, int):
                    references.append(f"Évaluation réglementaire v{assessment_version}")
                if isinstance(roadmap_version, int):
                    references.append(f"Roadmap v{roadmap_version}")
                document_version = result.structured_payload.get("document_version")
                if isinstance(document_version, int):
                    references.append(f"Document v{document_version}")
                if result.structured_payload.get("contract_analysis_id"):
                    references.append("Analyse contractuelle")
        elif outcome.failures and outcome.failures[0].error_code == "insufficient_evidence":
            answer = "Les sources réglementaires disponibles sont insuffisantes pour répondre de manière fiable."
        elif outcome.failures and outcome.failures[0].error_code == "contract_analysis_unavailable":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Une analyse contractuelle termin\u00e9e est requise avant de questionner ce contrat.",
            )
        elif outcome.failures and outcome.failures[0].structured_payload.get("provider_http_status") == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Copilot rate limit reached",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Copilot is temporarily unavailable",
            )

        public_warnings: list[str] = []
        if outcome.status == "partial":
            public_warnings.append("Une partie de l’analyse n’a pas pu être réalisée.")
        if outcome.results:
            public_warnings.extend(outcome.results[0].warnings)
        if outcome.results and outcome.results[0].structured_payload.get("evidence_status") == "PARTIAL":
            public_warnings.append("La couverture des sources est partielle. Les points non couverts sont signalés dans la réponse.")
        if (
            outcome.results
            and outcome.results[0].structured_payload.get("answer_source") not in {"PROJECT_GRAPH", "GENERAL_EXPLANATION"}
            and outcome.results[0].structured_payload.get("verification_verdict") != "pass"
        ):
            public_warnings.append("Certains éléments n’ont pas pu être vérifiés avec une fiabilité suffisante.")
        # Candidate capture is intentionally independent from generation. It
        # sees user-authored content only; a local capture failure must not
        # suppress a successfully generated Copilot answer.
        candidate_extraction_failed = False
        candidates = []
        try:
            candidates = await self._capture_candidates(
                actor,
                project_id=thread.subject_id,
                conversation_id=thread.id,
                message_id=user_message.id,
                content=user_message.content,
            )
        except Exception:
            candidate_extraction_failed = True
        candidate_payload = [
            {
                "id": str(candidate.id),
                "domain": candidate.domain,
                "value": candidate.value,
                "status": candidate.status,
                "operation": (candidate.provenance or {}).get("operation", "ADD"),
                "source": "COPILOT_CONVERSATION",
            }
            for candidate in candidates[:8]
        ]
        candidate_types = sorted({candidate.domain for candidate in candidates})
        assistant_message = await self.conversations.add_internal_message(
            thread.id,
            role="assistant",
            content=answer,
            parent_message_id=user_message.id,
            content_json={
                "sources": sources,
                "references": references,
                "warnings": public_warnings,
                "orchestration_status": outcome.status,
                "candidate_extraction_attempted": True,
                "candidate_extraction_failed": candidate_extraction_failed,
                "candidate_count": len(candidate_payload),
                "candidate_types": candidate_types,
                "knowledge_candidates": candidate_payload,
            },
        )
        await self.orchestrator.complete_copilot_turn(orchestration_request, outcome.root_run_id, pipeline_active=outcome.pipeline_active)
        return CopilotTurn(
            user_message=user_message,
            assistant_message=assistant_message,
            orchestration_status=outcome.status,
            sources=sources,
            references=references,
            warnings=public_warnings,
            candidate_extraction_attempted=True,
            candidate_count=len(candidate_payload),
            candidate_types=candidate_types,
            candidate_extraction_failed=candidate_extraction_failed,
        )
