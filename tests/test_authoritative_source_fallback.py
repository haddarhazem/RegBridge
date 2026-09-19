import uuid

import pytest

from app.modules.ai.contracts import AgentRequest, AuthorizedContext
from app.modules.ai.pipeline_types import EvidenceStatus, PipelineStage
from app.modules.regulatory.agent import RegulatoryAgent, _merge_evidence
from app.modules.regulatory.authoritative_sources import (
    MAX_DOCUMENTS_PER_SOURCE,
    MAX_EXCERPT_CHARS,
    MAX_SOURCES_PER_REQUEST,
    MAX_TOTAL_EVIDENCE,
    AuthoritativeRetrievalResult,
    AuthoritativeSource,
    AuthoritativeSourceError,
    AuthoritativeSourceRegistry,
    AuthoritativeSourceRetriever,
    OfficialHttpResponse,
    RetrievalStrategy,
    SourceRetrievalOutcome,
)
from app.modules.regulatory.contracts import RegulatoryEvidence
from app.modules.regulatory.evidence_sufficiency import QuestionScopeResolver
from app.modules.regulatory.verification import VerificationResult


async def public_dns(_host: str) -> list[str]:
    return ["8.8.8.8"]


def context(**values) -> AuthorizedContext:
    return AuthorizedContext(subject_type="project", subject_id=uuid.uuid4(), country_code="FR", **values)


def evidence(content: str, *, point_id: str | None = None, organization: str = "EUR-Lex") -> RegulatoryEvidence:
    return RegulatoryEvidence(
        point_id=point_id or str(uuid.uuid4()), rank=1, retrieval_score=0.1,
        organization=organization, content=content,
    )


class StaticTransport:
    def __init__(self, handler):
        self.handler = handler
        self.urls: list[str] = []

    async def get(self, url: str, *, timeout: float) -> OfficialHttpResponse:
        self.urls.append(url)
        response = self.handler(url)
        if isinstance(response, Exception):
            raise response
        return response


def html_response(text: str, *, status_code: int = 200, headers: dict[str, str] | None = None) -> OfficialHttpResponse:
    return OfficialHttpResponse(
        status_code=status_code,
        headers={"content-type": "text/html; charset=utf-8", **(headers or {})},
        text=text,
    )


def one_source(source: AuthoritativeSource) -> AuthoritativeSourceRegistry:
    registry = AuthoritativeSourceRegistry()
    registry.sources = (source,)
    return registry


def official_source() -> AuthoritativeSource:
    return AuthoritativeSource(
        source_id="test_eurlex", organization="EUR-Lex", base_domain="official.example",
        supported_domains=("AI",), allowed_hosts=("official.example",),
        search_url="https://official.example/search?q={query}",
    )


@pytest.mark.asyncio
async def test_registry_routes_only_approved_sources_and_respects_per_request_cap():
    registry = AuthoritativeSourceRegistry()
    assert [item.source_id for item in registry.select(["PRIVACY"], context())] == ["cnil"]
    assert [item.source_id for item in registry.select(["AI"], context(data_context="donnees personnelles"))] == ["eur_lex", "european_commission_digital"]
    assert [item.source_id for item in registry.select(["SECURITY_CLOUD"], context(technology="SaaS cloud"))] == ["anssi"]
    assert [item.source_id for item in registry.select(["SECURITY_CLOUD"], context(technology="SaaS cloud", data_context="donnees personnelles"))] == ["anssi", "cnil"]
    assert [item.source_id for item in registry.select(["ENERGY_IOT"], context(technology="compteurs IoT"))] == ["ecologie_gouv", "ademe"]
    assert [item.source_id for item in registry.select(["GENERAL_BUSINESS"], context())] == ["entreprendre_service_public", "service_public"]
    assert [item.source_id for item in registry.select(["CONTRACTS"], context())] == ["entreprendre_service_public", "service_public"]
    assert MAX_SOURCES_PER_REQUEST == 2


@pytest.mark.asyncio
async def test_official_retrieval_normalizes_bounded_evidence_without_raw_response():
    source = official_source()
    page = "<html><title>AI Act criteria</title><p>Un système d intelligence artificielle doit être classé selon sa finalité lorsque son déploiement relève des critères de risque applicables.</p></html>"
    transport = StaticTransport(lambda url: html_response(
        '<a href="/ai-act-criteria">AI Act classification criteres</a>' if "/search" in url else page
    ))
    retriever = AuthoritativeSourceRetriever(registry=one_source(source), transport=transport, host_resolver=public_dns)
    result = await retriever.retrieve(
        question="Quelle classification pour mon système IA au titre de l AI Act ?",
        domains=["AI"], scope=QuestionScopeResolver().resolve("Quelle classification pour mon système IA au titre de l AI Act ?"),
        context=context(technology="systeme intelligence artificielle"),
    )
    assert result.attempted_sources == ["test_eurlex"]
    assert result.succeeded_sources == ["test_eurlex"] and result.failed_sources == []
    assert result.source_outcomes == {"test_eurlex": SourceRetrievalOutcome.SUCCESS}
    assert len(result.evidence) == 1
    item = result.evidence[0]
    assert item.provenance_type == "LIVE_AUTHORITATIVE"
    assert item.organization == "EUR-Lex" and item.title == "AI Act criteria"
    assert item.retrieved_at is not None and item.url == "https://official.example/ai-act-criteria"
    assert len(item.content) <= MAX_EXCERPT_CHARS
    assert len(result.evidence) <= MAX_TOTAL_EVIDENCE and MAX_DOCUMENTS_PER_SOURCE == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "http://official.example/search", "file:///etc/passwd", "ftp://official.example/data",
    "https://localhost/search", "https://127.0.0.1/search", "https://[::1]/search",
    "https://192.168.1.10/search", "https://10.0.0.1/search", "https://evil.example/search",
    "https://user:password@official.example/search",
])
async def test_external_http_blocks_ssrf_protocols_credentials_and_unapproved_hosts(url):
    source = official_source()
    transport = StaticTransport(lambda _url: OfficialHttpResponse(status_code=200, text="unused"))
    retriever = AuthoritativeSourceRetriever(registry=one_source(source), transport=transport, host_resolver=public_dns)
    with pytest.raises(AuthoritativeSourceError):
        await retriever._fetch(url, source)
    assert transport.urls == []


@pytest.mark.asyncio
async def test_external_http_validates_redirect_target_before_following_it():
    source = official_source()
    transport = StaticTransport(lambda _url: OfficialHttpResponse(status_code=302, headers={"location": "https://127.0.0.1/private"}))
    retriever = AuthoritativeSourceRetriever(registry=one_source(source), transport=transport, host_resolver=public_dns)
    with pytest.raises(AuthoritativeSourceError):
        await retriever._fetch("https://official.example/search", source)
    assert transport.urls == ["https://official.example/search"]


@pytest.mark.asyncio
async def test_source_timeout_is_recorded_without_losing_existing_qdrant_evidence():
    registry = AuthoritativeSourceRegistry()
    anssi = next(source for source in registry.sources if source.source_id == "anssi")
    retriever = AuthoritativeSourceRetriever(
        registry=one_source(anssi), transport=StaticTransport(lambda _url: TimeoutError("controlled")), host_resolver=public_dns,
    )
    result = await retriever.retrieve(
        question="Quelles obligations de cybersécurité s appliquent à mon SaaS cloud ?",
        domains=["SECURITY_CLOUD"], scope=QuestionScopeResolver().resolve("Quelles obligations de cybersécurité s appliquent à mon SaaS cloud ?"),
        context=context(technology="SaaS cloud"),
    )
    qdrant = evidence("Les obligations de sécurité cloud sont applicables aux entreprises utilisant des services numériques.", organization="ANSSI")
    assert result.evidence == [] and result.failed_sources == ["anssi"]
    assert result.source_outcomes == {"anssi": SourceRetrievalOutcome.TIMEOUT}
    assert _merge_evidence([qdrant], result.evidence) == [qdrant]


@pytest.mark.asyncio
async def test_eurlex_stable_ai_act_document_normalizes_without_search_route():
    registry = AuthoritativeSourceRegistry()
    source = next(item for item in registry.sources if item.source_id == "eur_lex")
    assert source.retrieval_strategy is RetrievalStrategy.STABLE_DOCUMENT_PAGE
    transport = StaticTransport(lambda _url: html_response(
        "<title>Regulation (EU) 2024/1689</title><h1>Artificial Intelligence Act</h1>"
        "<p>Providers and deployers must assess the applicable risk classification criteria.</p>"
    ))
    retriever = AuthoritativeSourceRetriever(registry=one_source(source), transport=transport, host_resolver=public_dns)
    result = await retriever.retrieve(
        question="Quelles exigences de l AI Act concernent mon systeme d IA ?",
        domains=["AI"], scope=QuestionScopeResolver().resolve("Quelles exigences de l AI Act concernent mon systeme d IA ?"),
        context=context(technology="systeme intelligence artificielle"),
    )
    assert transport.urls == ["https://eur-lex.europa.eu/eli/reg/2024/1689/oj"]
    assert result.source_outcomes == {"eur_lex": SourceRetrievalOutcome.SUCCESS}
    assert result.succeeded_sources == ["eur_lex"] and len(result.evidence) == 1


@pytest.mark.asyncio
async def test_eurlex_404_and_commission_403_have_distinct_safe_classifications():
    registry = AuthoritativeSourceRegistry()
    eurlex = next(item for item in registry.sources if item.source_id == "eur_lex")
    commission = next(item for item in registry.sources if item.source_id == "european_commission_digital")
    transport = StaticTransport(lambda url: OfficialHttpResponse(
        status_code=404 if "eur-lex" in url else 403,
        headers={"content-type": "text/html"},
    ))
    retriever = AuthoritativeSourceRetriever(
        registry=one_source(eurlex), transport=transport, host_resolver=public_dns,
    )
    eurlex_result = await retriever.retrieve(
        question="AI Act", domains=["AI"], scope=QuestionScopeResolver().resolve("AI Act"), context=context(),
    )
    assert eurlex_result.source_outcomes == {"eur_lex": SourceRetrievalOutcome.HTTP_NOT_FOUND}
    retriever = AuthoritativeSourceRetriever(
        registry=one_source(commission), transport=transport, host_resolver=public_dns,
    )
    commission_result = await retriever.retrieve(
        question="AI Act", domains=["AI"], scope=QuestionScopeResolver().resolve("AI Act"), context=context(),
    )
    assert commission_result.source_outcomes == {"european_commission_digital": SourceRetrievalOutcome.ACCESS_DENIED}


@pytest.mark.asyncio
async def test_one_source_success_and_one_source_failure_preserves_the_successful_evidence():
    successful = official_source()
    successful = successful.model_copy(update={"source_id": "eur_lex"})
    denied = successful.model_copy(update={"source_id": "european_commission_digital", "organization": "European Commission", "base_domain": "commission.example", "allowed_hosts": ("commission.example",), "search_url": "https://commission.example/search?q={query}"})
    registry = AuthoritativeSourceRegistry()
    registry.sources = (successful, denied)
    transport = StaticTransport(lambda url: (
        html_response('<a href="/ai-act">AI Act classification</a>') if "official.example/search" in url
        else html_response("<title>AI Act</title><p>Applicable classification criteria for AI systems.</p>") if "official.example" in url
        else OfficialHttpResponse(status_code=403, headers={"content-type": "text/html"})
    ))
    retriever = AuthoritativeSourceRetriever(registry=registry, transport=transport, host_resolver=public_dns)
    result = await retriever.retrieve(
        question="AI Act classification", domains=["AI"], scope=QuestionScopeResolver().resolve("AI Act classification"), context=context(),
    )
    assert result.succeeded_sources == ["eur_lex"]
    assert result.failed_sources == ["european_commission_digital"]
    assert result.source_outcomes == {
        "eur_lex": SourceRetrievalOutcome.SUCCESS,
        "european_commission_digital": SourceRetrievalOutcome.ACCESS_DENIED,
    }
    assert len(result.evidence) == 1


@pytest.mark.asyncio
async def test_all_source_failures_remain_bounded_and_do_not_create_evidence():
    first = official_source()
    second = first.model_copy(update={"source_id": "second", "base_domain": "second.example", "allowed_hosts": ("second.example",), "search_url": "https://second.example/search?q={query}"})
    registry = AuthoritativeSourceRegistry()
    registry.sources = (first, second)
    retriever = AuthoritativeSourceRetriever(
        registry=registry,
        transport=StaticTransport(lambda _url: OfficialHttpResponse(status_code=404, headers={"content-type": "text/html"})),
        host_resolver=public_dns,
    )
    result = await retriever.retrieve(
        question="AI Act", domains=["AI"], scope=QuestionScopeResolver().resolve("AI Act"), context=context(),
    )
    assert result.evidence == [] and set(result.failed_sources) == {"test_eurlex", "second"}
    assert set(result.source_outcomes.values()) == {SourceRetrievalOutcome.HTTP_NOT_FOUND}


@pytest.mark.asyncio
async def test_non_text_content_is_rejected_as_invalid_content():
    source = official_source()
    retriever = AuthoritativeSourceRetriever(
        registry=one_source(source),
        transport=StaticTransport(lambda _url: OfficialHttpResponse(status_code=200, headers={"content-type": "application/pdf"}, text="%PDF")),
        host_resolver=public_dns,
    )
    result = await retriever.retrieve(
        question="AI Act", domains=["AI"], scope=QuestionScopeResolver().resolve("AI Act"), context=context(),
    )
    assert result.source_outcomes == {"test_eurlex": SourceRetrievalOutcome.INVALID_CONTENT}


class Recorder:
    def __init__(self): self.events = []
    async def start(self, stage, **kwargs): self.events.append(("start", stage, kwargs))
    async def succeed(self, stage, result=None): self.events.append(("succeed", stage, result or {}))
    async def fail(self, stage, **kwargs): self.events.append(("fail", stage, kwargs))


class PlannedRetriever:
    def __init__(self, *items): self.items = list(items); self.queries = []
    async def retrieve(self, question): self.queries.append(question); return self.items.pop(0)


class Provider:
    async def generate(self, _request):
        from app.modules.ai.llm import LLMGenerationResponse
        return LLMGenerationResponse(content="Réponse fondée.", model="fake")


class Verifier:
    async def verify(self, **_kwargs): return VerificationResult(verdict="pass", latency_ms=1)


class FakeAuthoritativeRetriever:
    def __init__(self, result: AuthoritativeRetrievalResult):
        self.registry = AuthoritativeSourceRegistry()
        self.result = result
        self.calls = 0
    async def retrieve(self, **_kwargs): self.calls += 1; return self.result


@pytest.mark.asyncio
async def test_agent_only_uses_authoritative_branch_after_qdrant_reassessment_is_partial():
    question = "Quelle classification de risque pour mon système IA au titre de l AI Act ?"
    generic = evidence("L AI Act contient des obligations générales et des catégories de risque pour les systèmes d intelligence artificielle.")
    official = evidence(
        "Un système d intelligence artificielle utilisant un algorithme doit être classé selon sa finalité lorsque son déploiement relève des critères de risque de l AI Act.",
        point_id="live-ai", organization="EUR-Lex",
    ).model_copy(update={"provenance_type": "LIVE_AUTHORITATIVE", "url": "https://official.example/ai-act", "title": "AI Act"})
    external = FakeAuthoritativeRetriever(AuthoritativeRetrievalResult(
        attempted_sources=["eur_lex"], succeeded_sources=["eur_lex"], evidence=[official],
    ))
    recorder = Recorder()
    agent = RegulatoryAgent(
        retriever=PlannedRetriever([generic], [generic]), provider=Provider(), verifier=Verifier(), authoritative_retriever=external,
        authoritative_fallback_enabled=True,
    )
    result = await agent.run(AgentRequest(
        request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), question=question, capability="regulatory", locale="fr",
        authorized_context=context(technology="algorithme d intelligence artificielle pour analyser la consommation"),
    ), pipeline=recorder)
    started = [stage for event, stage, _ in recorder.events if event == "start"]
    assert PipelineStage.RETRIEVING_AUTHORITATIVE_EVIDENCE in started
    assert PipelineStage.REASSESSING_AUTHORITATIVE_EVIDENCE in started
    assert external.calls == 1
    assert result.structured_payload["authoritative_fallback_attempted"] is True
    assert result.structured_payload["authoritative_status_before"] == EvidenceStatus.PARTIAL
    assert result.structured_payload["authoritative_status_after"] == EvidenceStatus.SUFFICIENT
    assert result.structured_payload["evidence_status"] == EvidenceStatus.SUFFICIENT


@pytest.mark.asyncio
async def test_agent_preserves_qdrant_evidence_and_partial_status_when_anssi_times_out():
    question = "Quelles obligations de cybersécurité s appliquent à mon SaaS cloud ?"
    qdrant = evidence(
        "Les obligations de sécurité cloud sont applicables aux entreprises utilisant des services numériques.",
        point_id="qdrant-cloud", organization="ANSSI",
    )
    external = FakeAuthoritativeRetriever(AuthoritativeRetrievalResult(
        attempted_sources=["anssi"], failed_sources=["anssi"], evidence=[],
    ))
    result = await RegulatoryAgent(
        retriever=PlannedRetriever([qdrant], [qdrant]), provider=Provider(), verifier=Verifier(),
        authoritative_retriever=external, authoritative_fallback_enabled=True,
    ).run(AgentRequest(
        request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), question=question, capability="regulatory", locale="fr",
        authorized_context=context(technology="plateforme SaaS cloud"),
    ), pipeline=Recorder())
    assert result.structured_payload["authoritative_sources_failed"] == "anssi"
    assert result.structured_payload["authoritative_status_before"] == EvidenceStatus.PARTIAL
    assert result.structured_payload["authoritative_status_after"] == EvidenceStatus.PARTIAL
    assert result.structured_payload["evidence_status"] == EvidenceStatus.PARTIAL
    assert any(item["point_id"] == "qdrant-cloud" for item in result.evidence)


@pytest.mark.asyncio
async def test_sufficient_qdrant_evidence_never_calls_authoritative_sources():
    class NeverAuthoritative:
        registry = AuthoritativeSourceRegistry()
        async def retrieve(self, **_kwargs): raise AssertionError("external retrieval must not start")

    result = await RegulatoryAgent(
        retriever=PlannedRetriever([evidence("Le RGPD est le cadre européen pour la protection des données personnelles.", organization="CNIL")]),
        provider=Provider(), verifier=Verifier(), authoritative_retriever=NeverAuthoritative(),
    ).run(AgentRequest(
        request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), question="What is RGPD?", capability="regulatory", locale="fr",
        authorized_context=context(),
    ), pipeline=Recorder())
    assert result.structured_payload["evidence_status"] == EvidenceStatus.SUFFICIENT
    assert result.structured_payload["authoritative_fallback_attempted"] is False
