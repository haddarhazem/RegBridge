"""Regression coverage for project facts, definitions, and regulatory questions."""

from __future__ import annotations

import uuid

import pytest

from app.modules.ai.contracts import AgentRequest, AuthorizedContext, OrchestrationRequest
from app.modules.ai.orchestration import DeterministicIntentClassifier
from app.modules.projects.knowledge_graph import GraphContextProvider, ProjectKnowledgeGraphBuilder, ProjectKnowledgeGraphProjection
from app.modules.regulatory.agent import RegulatoryAgent
from app.modules.regulatory.retrieval import RegulatoryRetrievalError


class CountingRetriever:
    def __init__(self) -> None:
        self.calls = 0

    async def retrieve(self, _question: str):
        self.calls += 1
        raise RegulatoryRetrievalError("controlled routing probe")


class NoGenerationProvider:
    async def generate(self, _request):
        raise AssertionError("Routing probes must not reach generation")


def _graph():
    return ProjectKnowledgeGraphBuilder().build(ProjectKnowledgeGraphProjection(
        project_id=uuid.uuid4(),
        display_name="Synthetic project",
        project_type="idea",
        country_code="FR",
        activity=None,
        sector="EnergyTech / SaaS B2B",
        technology="SaaS",
        data_context="données personnelles",
        target_market="France",
        location="Île-de-France, France",
        confirmed_fields=frozenset({"sector", "technology", "data", "market", "location"}),
    ))


async def _run(question: str):
    graph = _graph()
    retriever = CountingRetriever()
    result = await RegulatoryAgent(retriever=retriever, provider=NoGenerationProvider()).run(AgentRequest(
        request_id=uuid.uuid4(),
        parent_run_id=uuid.uuid4(),
        question=question,
        capability="regulatory",
        locale="fr",
        subject_type="project",
        subject_id=uuid.uuid4(),
        authorized_context=AuthorizedContext(
            subject_type="project",
            subject_id=uuid.uuid4(),
            graph_context=GraphContextProvider().select(graph, question),
        ),
    ))
    return result, retriever.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "C'est quoi un B2B ?",
    "Qu'est-ce que SaaS ?",
    "Que signifie EnergyTech ?",
    "Que signifie RGPD ?",
    "Qu'est-ce qu'une donnée personnelle ?",
    "C'est quoi un marché cible ?",
    "Et SaaS ?",
])
async def test_general_explanations_skip_project_graph_answers_and_regulatory_retrieval(question: str) -> None:
    result, retrieval_calls = await _run(question)

    assert result.structured_payload["answer_source"] == "GENERAL_EXPLANATION"
    assert result.structured_payload["regulatory_retrieval_skipped"] is True
    assert retrieval_calls == 0


@pytest.mark.asyncio
async def test_unresolved_definition_clarification_skips_regulatory_retrieval_without_history() -> None:
    result, retrieval_calls = await _run("Ça veut dire quoi ?")

    assert result.structured_payload["answer_source"] == "GENERAL_EXPLANATION"
    assert result.structured_payload["explanation_term"] is None
    assert retrieval_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("question, expected", [
    ("Quel est le secteur de ce projet ?", "EnergyTech / SaaS B2B"),
    ("Ce projet est-il B2B ?", "B2B"),
    ("Le secteur de ce projet contient-il B2B ?", "B2B"),
    ("Quel est le marché cible de ce projet ?", "France"),
])
async def test_project_specific_questions_use_only_the_trusted_graph(question: str, expected: str) -> None:
    result, retrieval_calls = await _run(question)

    assert expected in (result.answer or "")
    assert result.structured_payload["answer_source"] == "PROJECT_GRAPH"
    assert result.structured_payload["regulatory_retrieval_skipped"] is True
    assert retrieval_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("question", [
    "Le RGPD s'applique-t-il à un SaaS B2B ?",
    "Quelles obligations réglementaires concernent les données personnelles ?",
])
async def test_regulatory_questions_remain_in_the_regulatory_retrieval_path(question: str) -> None:
    result, retrieval_calls = await _run(question)

    assert result.structured_payload.get("answer_source") != "GENERAL_EXPLANATION"
    assert result.structured_payload.get("answer_source") != "PROJECT_GRAPH"
    assert retrieval_calls == 1


@pytest.mark.asyncio
async def test_existing_capability_classifier_remains_hint_driven() -> None:
    decision = await DeterministicIntentClassifier().classify(OrchestrationRequest(
        intent_hint="regulatory",
        question="C'est quoi un B2B ?",
    ))

    assert decision.capabilities == ["regulatory"]
