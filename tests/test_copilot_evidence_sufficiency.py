import uuid

import pytest

from app.modules.ai.contracts import AgentRequest, AuthorizedContext
from app.modules.ai.llm import LLMProviderError
from app.modules.ai.pipeline_types import EvidenceStatus, PipelineStage
from app.modules.regulatory.agent import RegulatoryAgent
from app.modules.regulatory.contracts import RegulatoryEvidence
from app.modules.regulatory.evidence_sufficiency import (
    EvidenceSufficiencyEvaluator,
    MissingDomainQueryBuilder,
    QuestionScope,
    QuestionScopeResolver,
    RequiredDomainResolver,
    ResolutionSource,
)
from app.modules.regulatory.retrieval import RegulatoryRetrievalError
from app.modules.regulatory.verification import VerificationResult


def item(content: str, *, organization: str = "CNIL") -> RegulatoryEvidence:
    return RegulatoryEvidence(point_id=str(uuid.uuid4()), rank=1, retrieval_score=0.01, organization=organization, content=content)


def context(**values) -> AuthorizedContext:
    return AuthorizedContext(subject_type="project", subject_id=uuid.uuid4(), **values)


def test_required_domain_resolver_is_question_scoped_and_never_defaults_unknown_to_general_business():
    resolver = RequiredDomainResolver()
    broad_context = context(
        country_code="FR", data_context="Données personnelles de clients",
        technology="AI/ML, plateforme SaaS cloud et compteurs IoT énergétiques",
    )

    assert resolver.resolve("What is RGPD?", broad_context).model_dump() == {
        "required_domains": ["PRIVACY"], "resolution_source": ResolutionSource.QUESTION_EXPLICIT,
        "matched_signals": ["question:rgpd"], "needs_clarification": False,
    }
    assert resolver.resolve("Qu'est-ce que le GDPR ?", broad_context).required_domains == ["PRIVACY"]
    rgbd = resolver.resolve("What is RGBD?", broad_context)
    assert rgbd.required_domains == [] and rgbd.resolution_source == ResolutionSource.UNRESOLVED and rgbd.needs_clarification
    assert resolver.resolve("Quelles obligations pour mon système d'IA ?", broad_context).required_domains == ["AI"]
    assert resolver.resolve("Quelles règles pour mon hébergement cloud ?", broad_context).required_domains == ["SECURITY_CLOUD"]
    assert resolver.resolve("Comment immatriculer ma société en France ?", broad_context).required_domains == ["GENERAL_BUSINESS"]
    assert resolver.resolve("Quelles obligations RGPD dois-je vérifier ?", broad_context).required_domains == ["PRIVACY"]
    broad = resolver.resolve("Quelles sont les principales obligations réglementaires pour mon projet en France ?", broad_context)
    assert broad.required_domains == ["GENERAL_BUSINESS", "PRIVACY", "AI", "SECURITY_CLOUD", "ENERGY_IOT"]
    enersight = context(
        country_code="FR",
        activity="EnerSight Demo est un service SaaS fictif de gestion énergétique.",
        technology="Plateforme SaaS, compteurs connectés et algorithmes d'analyse de consommation.",
        data_context="Coordonnées professionnelles des utilisateurs et relevés de compteurs.",
        location="France",
    )
    assert resolver.resolve("Quelles sont les principales obligations réglementaires pour mon projet en France ?", enersight).required_domains == [
        "GENERAL_BUSINESS", "PRIVACY", "SECURITY_CLOUD", "ENERGY_IOT",
    ]
    unknown = resolver.resolve("blabla inconnu", broad_context)
    assert unknown.required_domains == [] and unknown.resolution_source == ResolutionSource.UNRESOLVED and unknown.needs_clarification


def test_evidence_sufficiency_requires_resolved_domains_and_substantive_evidence():
    resolver, evaluator = RequiredDomainResolver(), EvidenceSufficiencyEvaluator()
    broad_context = context(data_context="Données personnelles", technology="AI/ML et cloud")
    privacy = item("La CNIL précise les obligations applicables au traitement des données personnelles.")
    generic = item("Les dispositifs de financement accompagnent les entreprises.", organization="Bpifrance Création")

    privacy_resolution = resolver.resolve("Quelles obligations RGPD dois-je vérifier ?", broad_context)
    assert evaluator.evaluate(privacy_resolution, [privacy]).status == EvidenceStatus.SUFFICIENT
    broad = resolver.resolve("Quelles sont les principales obligations réglementaires pour mon projet ?", broad_context)
    partial = evaluator.evaluate(broad, [privacy])
    assert partial.status == EvidenceStatus.PARTIAL and "PRIVACY" in partial.covered_domains
    combined = resolver.resolve("Quelles obligations concernent les données personnelles et l'IA ?", broad_context)
    assert evaluator.evaluate(combined, [generic]).status == EvidenceStatus.INSUFFICIENT
    assert evaluator.evaluate(privacy_resolution, []).status == EvidenceStatus.INSUFFICIENT
    assert evaluator.evaluate(privacy_resolution, [item("RGPD", organization="CNIL")]).status == EvidenceStatus.INSUFFICIENT
    assert resolver.resolve("What is RGBD?", broad_context).needs_clarification


def test_question_scope_resolver_uses_deterministic_specificity_precedence():
    resolver = QuestionScopeResolver()

    assert resolver.resolve("What is RGPD?").scope == QuestionScope.GENERAL_INFORMATION
    assert resolver.resolve("Quelles obligations generales dois-je respecter ?").scope == QuestionScope.GENERAL_OBLIGATIONS
    assert resolver.resolve("Quelles obligations s appliquent a mon SaaS cloud ?").scope == QuestionScope.PROJECT_SPECIFIC
    assert resolver.resolve("Quelles obligations sont specifiques au secteur des compteurs IoT ?").scope == QuestionScope.SECTOR_SPECIFIC
    assert resolver.resolve("Quelle classification et quel niveau de risque pour mon systeme IA ?").scope == QuestionScope.CLASSIFICATION_SPECIFIC


def test_scope_specificity_prevents_topical_evidence_from_being_a_false_positive():
    resolver = RequiredDomainResolver()
    scopes = QuestionScopeResolver()
    evaluator = EvidenceSufficiencyEvaluator()
    project = context(
        country_code="FR",
        technology="plateforme SaaS cloud et compteurs IoT energetiques",
        sector="gestion de l energie",
    )

    definition_question = "What is RGPD?"
    definition = item("Le RGPD est le cadre europeen pour la protection des donnees personnelles.")
    definition_assessment = evaluator.evaluate(
        resolver.resolve(definition_question, project), [definition], scopes.resolve(definition_question), project,
    )
    assert definition_assessment.status == EvidenceStatus.SUFFICIENT
    assert definition_assessment.scope_supported is True

    obligations_question = "Quelles obligations RGPD dois-je respecter ?"
    generic_privacy = item("Le RGPD assure la protection des donnees personnelles des personnes concernees.")
    obligations_assessment = evaluator.evaluate(
        resolver.resolve(obligations_question, project), [generic_privacy], scopes.resolve(obligations_question), project,
    )
    assert obligations_assessment.status == EvidenceStatus.PARTIAL
    assert obligations_assessment.scope_supported is False

    cloud_question = "Quelles obligations de securite cloud s appliquent a mon SaaS ?"
    generic_cloud = item("Les obligations de securite cloud sont applicables aux entreprises utilisant des services numeriques.", organization="ANSSI")
    cloud_assessment = evaluator.evaluate(
        resolver.resolve(cloud_question, project), [generic_cloud], scopes.resolve(cloud_question), project,
    )
    assert cloud_assessment.status == EvidenceStatus.PARTIAL
    assert cloud_assessment.covered_domains == ["SECURITY_CLOUD"]
    assert cloud_assessment.scope_supported is False

    sector_question = "Quelles obligations sont specifiques au secteur des compteurs IoT energetiques ?"
    generic_iot = item("Les obligations applicables aux compteurs IoT energetiques concernent les entreprises qui les exploitent.", organization="CRE")
    sector_assessment = evaluator.evaluate(
        resolver.resolve(sector_question, project), [generic_iot], scopes.resolve(sector_question), project,
    )
    assert sector_assessment.status == EvidenceStatus.PARTIAL
    assert sector_assessment.covered_domains == ["ENERGY_IOT"]
    assert sector_assessment.scope_supported is False

    classification_question = "Quelle classification de risque pour mon systeme IA au titre de l AI Act ?"
    generic_ai = item("L AI Act contient des obligations generales et des categories de risque pour les systemes d intelligence artificielle.", organization="Commission europeenne")
    classification_assessment = evaluator.evaluate(
        resolver.resolve(classification_question, project), [generic_ai], scopes.resolve(classification_question), project,
    )
    assert classification_assessment.status == EvidenceStatus.PARTIAL
    assert classification_assessment.covered_domains == ["AI"]
    assert classification_assessment.scope_supported is False

    missing_ai = evaluator.evaluate(
        resolver.resolve(classification_question, project), [general_evidence()], scopes.resolve(classification_question), project,
    )
    assert missing_ai.status == EvidenceStatus.INSUFFICIENT


def test_specificity_rules_accept_evidence_only_when_it_binds_conditions_to_confirmed_context():
    resolver = RequiredDomainResolver()
    scopes = QuestionScopeResolver()
    evaluator = EvidenceSufficiencyEvaluator()

    ai_question = "Quelle classification de risque pour mon systeme IA au titre de l AI Act ?"
    ai_context = context(technology="algorithme d intelligence artificielle pour analyser la consommation")
    ai_evidence = item(
        "Un systeme d intelligence artificielle utilisant un algorithme doit etre classe selon sa finalite "
        "lorsque son deploiement releve des criteres de risque de l AI Act.",
        organization="Commission europeenne",
    )
    assert evaluator.evaluate(
        resolver.resolve(ai_question, ai_context), [ai_evidence], scopes.resolve(ai_question), ai_context,
    ).status == EvidenceStatus.SUFFICIENT

    iot_question = "Quelles obligations sont specifiques au secteur des compteurs IoT energetiques ?"
    iot_context = context(technology="compteurs IoT energetiques")
    iot_evidence = item(
        "L exploitant d un compteur IoT energetique doit respecter ces obligations lorsque le dispositif est deploye.",
        organization="CRE",
    )
    assert evaluator.evaluate(
        resolver.resolve(iot_question, iot_context), [iot_evidence], scopes.resolve(iot_question), iot_context,
    ).status == EvidenceStatus.SUFFICIENT


def test_scope_aware_fallback_query_adds_only_canonical_scope_terms():
    built = MissingDomainQueryBuilder().build(
        "Quelle classification de risque pour mon systeme IA au titre de l AI Act ?",
        "AI",
        context(technology="systeme IA"),
        QuestionScopeResolver().resolve("Quelle classification de risque pour mon systeme IA au titre de l AI Act ?"),
    )
    assert "classification niveau risque" in built
    assert "criteres applicabilite" in built
    assert len(built) <= 500


class Recorder:
    def __init__(self): self.events = []
    async def start(self, stage, **kwargs): self.events.append(("start", stage, kwargs))
    async def succeed(self, stage, result=None): self.events.append(("succeed", stage, result or {}))
    async def fail(self, stage, **kwargs): self.events.append(("fail", stage, kwargs))


class Retriever:
    def __init__(self, evidence): self.evidence = evidence
    async def retrieve(self, question): return self.evidence


class PlannedRetriever:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.queries = []

    async def retrieve(self, question):
        self.queries.append(question)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FailingRetriever:
    async def retrieve(self, question): raise RegulatoryRetrievalError("controlled retrieval failure")


class Provider:
    async def generate(self, request):
        from app.modules.ai.llm import LLMGenerationResponse
        return LLMGenerationResponse(content="Réponse fondée.", model="fake")


class RateLimitedProvider:
    async def generate(self, request):
        error = LLMProviderError("controlled rate limit"); error.http_status = 429
        raise error


class Verifier:
    async def verify(self, **kwargs): return VerificationResult(verdict="pass", latency_ms=1)


class BlockingVerifier:
    async def verify(self, **kwargs): return VerificationResult(verdict="block", reasons=["controlled block"], latency_ms=1)


class UnexpectedCall:
    async def retrieve(self, question): raise AssertionError("retrieval must not start")
    async def generate(self, request): raise AssertionError("generation must not start")


def request(question: str) -> AgentRequest:
    return AgentRequest(request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), question=question, capability="regulatory", locale="fr", authorized_context=context())


def broad_request() -> AgentRequest:
    return AgentRequest(
        request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), capability="regulatory", locale="fr",
        question="Quelles sont les principales obligations reglementaires pour une entreprise en France ?",
        authorized_context=context(
            country_code="FR", data_context="Données personnelles de clients",
            technology="AI/ML",
            activity="PRIVATE PROJECT DESCRIPTION MUST NOT ENTER RETRIEVAL QUERIES",
        ),
    )


def general_evidence(point_id: str | None = None) -> RegulatoryEvidence:
    value = item("Les obligations et formalités applicables concernent les entreprises françaises.", organization="Entreprendre Service-Public.fr")
    return value.model_copy(update={"point_id": point_id}) if point_id else value


def privacy_evidence() -> RegulatoryEvidence:
    return item("La CNIL précise les obligations applicables au traitement des données personnelles.")


def ai_evidence() -> RegulatoryEvidence:
    return item("Les obligations applicables aux systèmes d'intelligence artificielle doivent être vérifiées.", organization="CNIL")


def test_missing_domain_query_builder_is_deterministic_bounded_and_excludes_project_description():
    built = MissingDomainQueryBuilder().build(
        "Quelles sont les principales obligations réglementaires pour mon projet en France ?",
        "SECURITY_CLOUD",
        context(technology="plateforme SaaS cloud"),
    )
    assert "cybersecurite" in built and "securite cloud" in built and "saas" in built
    assert "PRIVATE" not in built and len(built) <= 500


@pytest.mark.asyncio
async def test_scope_gap_triggers_bounded_fallback_even_when_the_domain_is_covered():
    question = "Quelles obligations sont specifiques au secteur des compteurs IoT energetiques ?"
    initial = item(
        "Les obligations applicables aux compteurs IoT energetiques concernent les entreprises qui les exploitent.",
        organization="CRE",
    )
    retriever = PlannedRetriever([initial], [initial])
    result = await RegulatoryAgent(retriever=retriever, provider=Provider(), verifier=Verifier()).run(
        AgentRequest(
            request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), question=question,
            capability="regulatory", locale="fr",
            authorized_context=context(country_code="FR", sector="gestion de l energie", technology="compteurs IoT energetiques"),
        ),
        pipeline=Recorder(),
    )

    assert len(retriever.queries) == 2
    assert "obligations sectorielles" in retriever.queries[1]
    assert result.structured_payload["fallback_attempted"] is True
    assert result.structured_payload["fallback_domains"] == "ENERGY_IOT"
    assert result.structured_payload["initial_scope_supported"] is False
    assert result.structured_payload["final_scope_supported"] is False
    assert result.structured_payload["evidence_status"] == "PARTIAL"


@pytest.mark.asyncio
async def test_unresolved_rgbd_skips_retrieval_and_generation_and_returns_clarification():
    recorder = Recorder()
    result = await RegulatoryAgent(retriever=UnexpectedCall(), provider=UnexpectedCall(), verifier=Verifier()).run(request("What is RGBD?"), pipeline=recorder)
    assert result.status == "succeeded" and "RGBD" in result.answer
    assert result.structured_payload["resolution_source"] == "UNRESOLVED"
    assert result.structured_payload["needs_clarification"] is True
    assert [stage for event, stage, _ in recorder.events if event == "start"] == [PipelineStage.ASSESSING_EVIDENCE]
    assert PipelineStage.RETRIEVING_EVIDENCE not in [stage for _, stage, _ in recorder.events]


@pytest.mark.asyncio
async def test_agent_records_real_ordered_stages_and_skips_generation_for_insufficient_evidence():
    recorder = Recorder()
    result = await RegulatoryAgent(retriever=Retriever([]), provider=Provider(), verifier=Verifier()).run(request("Quelles obligations RGPD dois-je vérifier ?"), pipeline=recorder)
    assert result.status == "succeeded" and result.structured_payload["evidence_status"] == "INSUFFICIENT"
    assert [stage for event, stage, _ in recorder.events if event == "start"] == [
        PipelineStage.RETRIEVING_EVIDENCE,
        PipelineStage.ASSESSING_EVIDENCE,
        PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE,
        PipelineStage.REASSESSING_EVIDENCE,
    ]
    assert PipelineStage.GENERATING not in [stage for _, stage, _ in recorder.events]


@pytest.mark.asyncio
async def test_sufficient_initial_evidence_does_not_attempt_fallback():
    retriever = PlannedRetriever([privacy_evidence()])
    result = await RegulatoryAgent(retriever=retriever, provider=Provider(), verifier=Verifier()).run(
        request("Qu'est-ce que le RGPD ?"), pipeline=Recorder()
    )
    assert len(retriever.queries) == 1
    assert result.structured_payload["fallback_attempted"] is False
    assert result.structured_payload["evidence_status"] == "SUFFICIENT"


@pytest.mark.asyncio
async def test_partial_fallback_targets_only_missing_domains_and_truthfully_remains_partial():
    retriever = PlannedRetriever([general_evidence()], [privacy_evidence()], [])
    result = await RegulatoryAgent(retriever=retriever, provider=Provider(), verifier=Verifier()).run(broad_request(), pipeline=Recorder())
    assert len(retriever.queries) == 3
    assert "rgpd" in retriever.queries[1] and "ai act" in retriever.queries[2]
    assert result.structured_payload["initial_evidence_status"] == "PARTIAL"
    assert result.structured_payload["fallback_domains"] == "PRIVACY, AI"
    assert result.structured_payload["final_covered_domains"] == "GENERAL_BUSINESS, PRIVACY"
    assert result.structured_payload["final_missing_domains"] == "AI"
    assert result.structured_payload["evidence_status"] == "PARTIAL"


@pytest.mark.asyncio
async def test_full_fallback_recovery_reuses_the_same_evaluator_before_generation():
    retriever = PlannedRetriever([general_evidence()], [privacy_evidence()], [ai_evidence()])
    result = await RegulatoryAgent(retriever=retriever, provider=Provider(), verifier=Verifier()).run(broad_request(), pipeline=Recorder())
    assert result.structured_payload["initial_evidence_status"] == "PARTIAL"
    assert result.structured_payload["final_evidence_status"] == "SUFFICIENT"
    assert result.structured_payload["evidence_status"] == "SUFFICIENT"
    assert result.structured_payload["fallback_unique_evidence_count"] == 2


@pytest.mark.asyncio
async def test_fallback_deduplicates_stable_point_ids_before_generation():
    initial = general_evidence("point-123")
    duplicate = initial.model_copy(update={"rank": 1})
    retriever = PlannedRetriever([initial], [duplicate], [])
    result = await RegulatoryAgent(retriever=retriever, provider=Provider(), verifier=Verifier()).run(broad_request(), pipeline=Recorder())
    assert [item["point_id"] for item in result.evidence].count("point-123") == 1
    assert result.structured_payload["fallback_unique_evidence_count"] == 0


@pytest.mark.asyncio
async def test_partial_fallback_failure_preserves_other_domains_and_localizes_the_failure():
    recorder = Recorder()
    retriever = PlannedRetriever([general_evidence()], [privacy_evidence()], RegulatoryRetrievalError("AI unavailable"))
    result = await RegulatoryAgent(retriever=retriever, provider=Provider(), verifier=Verifier()).run(broad_request(), pipeline=recorder)
    assert result.status == "succeeded"
    assert result.structured_payload["fallback_failed_domains"] == "AI"
    assert result.structured_payload["final_covered_domains"] == "GENERAL_BUSINESS, PRIVACY"
    fallback = next(detail for event, stage, detail in recorder.events if event == "succeed" and stage == PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE)
    assert fallback["fallback_failure_count"] == 1


@pytest.mark.asyncio
async def test_complete_fallback_failure_is_distinct_from_initial_retrieval_failure():
    recorder = Recorder()
    retriever = PlannedRetriever([general_evidence()], RegulatoryRetrievalError("privacy unavailable"), RegulatoryRetrievalError("ai unavailable"))
    result = await RegulatoryAgent(retriever=retriever, provider=UnexpectedCall(), verifier=Verifier()).run(broad_request(), pipeline=recorder)
    assert result.status == "succeeded" and result.structured_payload["generation_skipped"] is True
    assert result.structured_payload["fallback_failure_code"] == "FALLBACK_RETRIEVAL_FAILED"
    assert result.evidence and result.evidence[0]["organization"] == "Entreprendre Service-Public.fr"
    assert any(event == "fail" and stage == PipelineStage.RETRIEVING_MISSING_DOMAIN_EVIDENCE and detail["error_code"] == "FALLBACK_RETRIEVAL_FAILED" for event, stage, detail in recorder.events)
    started = [stage for event, stage, _ in recorder.events if event == "start"]
    assert PipelineStage.REASSESSING_EVIDENCE not in started and PipelineStage.GENERATING not in started


@pytest.mark.asyncio
async def test_agent_localizes_retrieval_provider_and_verifier_failures_without_starting_later_stages():
    privacy_evidence = [item("La CNIL précise les obligations applicables au traitement des données personnelles.")]
    retrieval_recorder = Recorder()
    retrieval = await RegulatoryAgent(retriever=FailingRetriever(), provider=Provider(), verifier=Verifier()).run(request("Quelles obligations RGPD dois-je vérifier ?"), pipeline=retrieval_recorder)
    assert retrieval.status == "failed"
    assert any(event == "fail" and stage == PipelineStage.RETRIEVING_EVIDENCE and detail["error_code"] == "QDRANT_UNAVAILABLE" for event, stage, detail in retrieval_recorder.events)
    assert PipelineStage.ASSESSING_EVIDENCE not in [stage for event, stage, _ in retrieval_recorder.events if event == "start"]

    provider_recorder = Recorder()
    provider = await RegulatoryAgent(retriever=Retriever(privacy_evidence), provider=RateLimitedProvider(), verifier=Verifier()).run(request("Quelles obligations RGPD dois-je vérifier ?"), pipeline=provider_recorder)
    assert provider.status == "failed"
    assert any(event == "fail" and stage == PipelineStage.GENERATING and detail["error_code"] == "PROVIDER_RATE_LIMIT" for event, stage, detail in provider_recorder.events)
    assert PipelineStage.VERIFYING not in [stage for event, stage, _ in provider_recorder.events if event == "start"]

    verifier_recorder = Recorder()
    verified = await RegulatoryAgent(retriever=Retriever(privacy_evidence), provider=Provider(), verifier=BlockingVerifier()).run(request("Quelles obligations RGPD dois-je vérifier ?"), pipeline=verifier_recorder)
    assert verified.status == "succeeded"
    assert any(event == "fail" and stage == PipelineStage.VERIFYING and detail["error_code"] == "VERIFICATION_BLOCKED" for event, stage, detail in verifier_recorder.events)
