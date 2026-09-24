from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.modules.ai.contracts import AgentRequest, AgentResult, AuthorizedContext, OrchestrationRequest, OrchestrationResult
from app.modules.ai.copilot import ProjectCopilotService, _copilot_intent
from app.modules.ai.orchestration import DeterministicIntentClassifier
from app.modules.ai.projections import ContractAnalysisProjection, ContractClauseProjection
from app.modules.documents.contract_agent import ContractAgent
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.regulatory.orchestration import build_contract_orchestrator


def analysis_context() -> AuthorizedContext:
    document_id, version_id = uuid.uuid4(), uuid.uuid4()
    clauses = [
        ContractClauseProjection(
            id=uuid.uuid4(), clause_type="liability", title="Liability", status="AMBIGUOUS", risk_level="high",
            source_text="The provider liability is unlimited.", source_location="Liability - characters 0-42",
            verification_status="VERIFIED",
            evidence_quotes=["The provider liability is unlimited."],
            plain_language_summary="No liability cap was identified.", purpose="Allocates financial consequences.",
            issues=["No clear cap was identified."], why_it_matters="Financial exposure may be material.",
            recommendation="Review an appropriate liability cap.", suggested_revision="Provide a liability cap.",
        ),
        ContractClauseProjection(
            id=uuid.uuid4(), clause_type="termination", title="Termination", status="MISSING", risk_level="medium",
            source_text="", source_location=None, plain_language_summary="No termination clause was detected.",
            verification_status="VERIFIED",
            purpose="Organizes early contract termination.", issues=["No mechanism was detected."],
            why_it_matters="Early exit remains uncertain.", recommendation="Review whether a termination clause is needed.",
        ),
        ContractClauseProjection(
            id=uuid.uuid4(), clause_type="intellectual_property", title="Intellectual property", status="AMBIGUOUS", risk_level="high",
            source_text="Intellectual property will be defined later.", source_location="IP - characters 43-88",
            verification_status="VERIFIED",
            plain_language_summary="The rights holder is not clearly identified.", purpose="Determines rights in deliverables.",
            issues=["Rights holder is not determined."], why_it_matters="Rights could be disputed.", recommendation="Identify the rights holder.",
        ),
    ]
    return AuthorizedContext(
        subject_type="project", subject_id=uuid.uuid4(),
        contract_analysis=ContractAnalysisProjection(
            id=uuid.uuid4(), document_id=document_id, document_version_id=version_id, status="completed",
            summary="Two clauses need priority review.", clauses=clauses,
        ),
    )


async def ask(question: str):
    context = analysis_context()
    return await ContractAgent().run(AgentRequest(
        request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), question=question, capability="contract", locale="fr",
        subject_type="project", subject_id=context.subject_id, authorized_context=context,
    ))


@pytest.mark.asyncio
async def test_contract_agent_answers_from_structured_analysis_without_hallucinating_absent_clauses():
    result = await ask("Le contrat contient-il une clause de non-concurrence ?")
    assert "identifi" in result.answer
    assert result.structured_payload["answer_source"] == "CONTRACT_ANALYSIS"

    penalty = await ask("Quelle est la penalite prevue en cas de retard ?")
    assert "identifi" in penalty.answer
    assert "inventer" in penalty.answer

    termination = await ask("Y a-t-il une clause de resiliation ?")
    assert "identifi" in termination.answer


@pytest.mark.asyncio
async def test_contract_agent_explains_risks_and_preserves_legal_scope_boundary():
    risks = await ask("Quels sont les principaux risques de ce contrat ?")
    assert "Liability" in risks.answer and "cap" in risks.answer.casefold()

    intellectual_property = await ask("Que prevoit le contrat sur la propriete intellectuelle ?")
    assert "titulaire" in intellectual_property.answer.casefold() or "rights" in intellectual_property.answer.casefold()

    liability = await ask("Que prevoit le contrat sur la responsabilite ?")
    assert "Preuve du contrat" in liability.answer
    assert "The provider liability is unlimited." in liability.answer

    legal = await ask("Ce contrat est-il legal ?")
    assert "confirmer" in legal.answer
    assert "Liability" in legal.answer


@pytest.mark.asyncio
async def test_contract_and_regulatory_routing_stay_separate_with_a_safe_boundary():
    document_id, analysis_id = uuid.uuid4(), uuid.uuid4()
    assert _copilot_intent("Que prevoit ce contrat concernant la propriete intellectuelle ?", document_id=None, analysis_id=None) == "contract"
    assert _copilot_intent("Que dit le RGPD sur le traitement des donnees personnelles ?", document_id=None, analysis_id=None) == "regulatory"
    assert _copilot_intent("Cette clause de traitement des donnees respecte-t-elle le RGPD ?", document_id=document_id, analysis_id=analysis_id) == "contract"

    classifier = DeterministicIntentClassifier()
    assert (await classifier.classify(OrchestrationRequest(intent_hint="contract"))).capabilities == ["contract"]
    assert (await classifier.classify(OrchestrationRequest(intent_hint="regulatory"))).capabilities == ["regulatory"]


def test_contract_orchestrator_does_not_construct_a_regulatory_capability():
    orchestrator = build_contract_orchestrator(SimpleNamespace())

    assert isinstance(orchestrator.router.registry.resolve("contract"), ContractAgent)
    with pytest.raises(ValueError):
        orchestrator.router.registry.resolve("regulatory")


@pytest.mark.asyncio
async def test_missing_contract_analysis_is_an_actionable_conflict_not_a_generic_service_error():
    actor = AuthenticatedPrincipal(user_id=uuid.uuid4(), email="contract-test@example.test", roles=(), provider="test")
    project_id, document_id, version_id, conversation_id = (uuid.uuid4() for _ in range(4))
    thread = SimpleNamespace(id=conversation_id, subject_type="project", subject_id=project_id)
    user_message = SimpleNamespace(id=uuid.uuid4(), content="Quels sont les risques de ce contrat ?")
    conversations = SimpleNamespace(
        get_thread=AsyncMock(return_value=thread),
        add_user_message=AsyncMock(return_value=user_message),
    )
    outcome = OrchestrationResult(
        request_id=uuid.uuid4(),
        status="failed",
        selected_capabilities=["contract"],
        failures=[AgentResult(agent_name="contract-agent", capability="contract", status="failed", error_code="contract_analysis_unavailable")],
    )
    orchestrator = SimpleNamespace(run=AsyncMock(return_value=outcome))

    with pytest.raises(HTTPException) as error:
        await ProjectCopilotService(conversations, orchestrator).respond(
            actor,
            conversation_id,
            user_message.content,
            document_id=document_id,
            document_version_id=version_id,
        )

    assert error.value.status_code == 409
    assert "analyse contractuelle" in error.value.detail
    assert "questionner" in error.value.detail
    request = orchestrator.run.await_args.args[0]
    assert request.context_document_id == document_id
    assert request.context_version_id == version_id
    assert request.context_analysis_id is None
    assert request.intent_hint == "contract"
