"""Authenticated project Copilot over the approved production orchestrator."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.modules.ai.contracts import OrchestrationRequest
from app.modules.ai.orchestration import Orchestrator
from app.modules.ai.services import ConversationService
from app.modules.identity.schemas import AuthenticatedPrincipal


@dataclass(frozen=True)
class CopilotTurn:
    user_message: object
    assistant_message: object
    orchestration_status: str
    sources: list[str]
    references: list[str]
    warnings: list[str]


class ProjectCopilotService:
    def __init__(self, conversation_service: ConversationService, orchestrator: Orchestrator) -> None:
        self.conversations = conversation_service
        self.orchestrator = orchestrator

    async def respond(
        self,
        actor: AuthenticatedPrincipal,
        thread_id: uuid.UUID,
        content: str,
    ) -> CopilotTurn:
        thread = await self.conversations.get_thread(actor, thread_id)
        if thread.subject_type != "project" or thread.subject_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A project-scoped conversation is required",
            )

        user_message = await self.conversations.add_user_message(actor, thread.id, content)
        outcome = await self.orchestrator.run(OrchestrationRequest(
            conversation_id=thread.id,
            message_id=user_message.id,
            question=content,
            principal=actor,
            subject_type="project",
            subject_id=thread.subject_id,
            intent_hint="regulatory",
            locale="fr",
        ))
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
        elif outcome.failures and outcome.failures[0].error_code == "insufficient_evidence":
            answer = "Les sources réglementaires disponibles sont insuffisantes pour répondre de manière fiable."
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Copilot is temporarily unavailable",
            )

        public_warnings: list[str] = []
        if outcome.status == "partial":
            public_warnings.append("Une partie de l’analyse n’a pas pu être réalisée.")
        if outcome.results and outcome.results[0].structured_payload.get("verification_verdict") != "pass":
            public_warnings.append("Certains éléments n’ont pas pu être vérifiés avec une fiabilité suffisante.")
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
            },
        )
        return CopilotTurn(
            user_message=user_message,
            assistant_message=assistant_message,
            orchestration_status=outcome.status,
            sources=sources,
            references=references,
            warnings=public_warnings,
        )
