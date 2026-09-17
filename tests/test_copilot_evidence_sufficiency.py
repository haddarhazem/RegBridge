import uuid

import pytest

from app.modules.ai.contracts import AgentRequest, AuthorizedContext
from app.modules.ai.llm import LLMProviderError
from app.modules.ai.pipeline_types import EvidenceStatus, PipelineStage
from app.modules.regulatory.agent import RegulatoryAgent
from app.modules.regulatory.contracts import RegulatoryEvidence
from app.modules.regulatory.evidence_sufficiency import EvidenceSufficiencyEvaluator
from app.modules.regulatory.retrieval import RegulatoryRetrievalError
from app.modules.regulatory.verification import VerificationResult


def item(content: str, *, organization: str = "CNIL") -> RegulatoryEvidence:
    return RegulatoryEvidence(point_id=str(uuid.uuid4()), rank=1, retrieval_score=0.01, organization=organization, content=content)


def context(**values) -> AuthorizedContext:
    return AuthorizedContext(subject_type="project", subject_id=uuid.uuid4(), **values)


def test_evidence_sufficiency_is_deterministic_and_question_scoped():
    evaluator = EvidenceSufficiencyEvaluator()
    privacy = item("La CNIL précise les obligations applicables au traitement des données personnelles.")
    generic = item("Les dispositifs de financement accompagnent les entreprises.", organization="Bpifrance Création")
    broad_context = context(data_context="Données personnelles", technology="AI/ML et cloud")

    assert evaluator.evaluate("Quelles obligations RGPD dois-je vérifier ?", broad_context, [privacy]).status == EvidenceStatus.SUFFICIENT
    partial = evaluator.evaluate("Quelles sont les principales obligations réglementaires pour mon projet ?", broad_context, [privacy])
    assert partial.status == EvidenceStatus.PARTIAL
    assert "PRIVACY" in partial.covered_domains
    assert {"AI", "SECURITY_CLOUD"}.issubset(partial.missing_domains)
    assert evaluator.evaluate("Quelles obligations concernent les données personnelles et l'IA ?", broad_context, [generic]).status == EvidenceStatus.INSUFFICIENT
    assert evaluator.evaluate("Quelles obligations RGPD dois-je vérifier ?", broad_context, []).status == EvidenceStatus.INSUFFICIENT
    assert evaluator.evaluate("Quelles obligations RGPD dois-je vérifier ?", broad_context, [item("RGPD", organization="CNIL")]).status == EvidenceStatus.INSUFFICIENT

    privacy_only = evaluator.required_domains("Quelles obligations RGPD dois-je vérifier ?", broad_context)
    assert privacy_only == ["PRIVACY"]


class Recorder:
    def __init__(self):
        self.events = []

    async def start(self, stage, **kwargs):
        self.events.append(("start", stage, kwargs))

    async def succeed(self, stage, result=None):
        self.events.append(("succeed", stage, result or {}))

    async def fail(self, stage, **kwargs):
        self.events.append(("fail", stage, kwargs))


class Retriever:
    def __init__(self, evidence): self.evidence = evidence
    async def retrieve(self, question): return self.evidence


class Provider:
    async def generate(self, request):
        from app.modules.ai.llm import LLMGenerationResponse
        return LLMGenerationResponse(content="Réponse fondée.", model="fake")


class Verifier:
    async def verify(self, **kwargs):
        return VerificationResult(verdict="pass", latency_ms=1)


class FailingRetriever:
    async def retrieve(self, question):
        raise RegulatoryRetrievalError("controlled retrieval failure")


class RateLimitedProvider:
    async def generate(self, request):
        error = LLMProviderError("controlled rate limit")
        error.http_status = 429
        raise error


class BlockingVerifier:
    async def verify(self, **kwargs):
        return VerificationResult(verdict="block", reasons=["controlled block"], latency_ms=1)


@pytest.mark.asyncio
async def test_agent_records_real_ordered_stages_and_skips_generation_for_insufficient_evidence():
    recorder = Recorder()
    agent = RegulatoryAgent(retriever=Retriever([]), provider=Provider(), verifier=Verifier())
    result = await agent.run(AgentRequest(request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), question="Quelles obligations RGPD dois-je vérifier ?", capability="regulatory", locale="fr", authorized_context=context()), pipeline=recorder)

    assert result.status == "succeeded"
    assert result.structured_payload["evidence_status"] == "INSUFFICIENT"
    assert [stage for event, stage, _ in recorder.events if event == "start"] == [PipelineStage.RETRIEVING_EVIDENCE, PipelineStage.ASSESSING_EVIDENCE]
    assert PipelineStage.GENERATING not in [stage for _, stage, _ in recorder.events]
    assert PipelineStage.VERIFYING not in [stage for _, stage, _ in recorder.events]


@pytest.mark.asyncio
async def test_agent_localizes_retrieval_provider_and_verifier_failures_without_starting_later_stages():
    request = AgentRequest(
        request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(),
        question="Quelles obligations RGPD dois-je vérifier ?", capability="regulatory",
        locale="fr", authorized_context=context(),
    )
    privacy_evidence = [item("La CNIL précise les obligations applicables au traitement des données personnelles.")]

    retrieval_recorder = Recorder()
    retrieval = await RegulatoryAgent(
        retriever=FailingRetriever(), provider=Provider(), verifier=Verifier(),
    ).run(request, pipeline=retrieval_recorder)
    assert retrieval.status == "failed"
    assert ("fail", PipelineStage.RETRIEVING_EVIDENCE, {"error_code": "QDRANT_UNAVAILABLE", "error_message": "Regulatory sources are temporarily unavailable"}) in retrieval_recorder.events
    assert PipelineStage.ASSESSING_EVIDENCE not in [stage for event, stage, _ in retrieval_recorder.events if event == "start"]

    provider_recorder = Recorder()
    provider = await RegulatoryAgent(
        retriever=Retriever(privacy_evidence), provider=RateLimitedProvider(), verifier=Verifier(),
    ).run(request, pipeline=provider_recorder)
    assert provider.status == "failed"
    assert any(event == "fail" and stage == PipelineStage.GENERATING and detail["error_code"] == "PROVIDER_RATE_LIMIT" for event, stage, detail in provider_recorder.events)
    assert PipelineStage.VERIFYING not in [stage for event, stage, _ in provider_recorder.events if event == "start"]

    verifier_recorder = Recorder()
    verified = await RegulatoryAgent(
        retriever=Retriever(privacy_evidence), provider=Provider(), verifier=BlockingVerifier(),
    ).run(request, pipeline=verifier_recorder)
    assert verified.status == "succeeded"
    assert [stage for event, stage, _ in verifier_recorder.events if event == "start"] == [
        PipelineStage.RETRIEVING_EVIDENCE,
        PipelineStage.ASSESSING_EVIDENCE,
        PipelineStage.GENERATING,
        PipelineStage.VERIFYING,
    ]
    assert any(event == "fail" and stage == PipelineStage.VERIFYING and detail["error_code"] == "VERIFICATION_BLOCKED" for event, stage, detail in verifier_recorder.events)
