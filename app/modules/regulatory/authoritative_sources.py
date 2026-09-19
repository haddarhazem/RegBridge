"""Bounded retrieval from an explicit registry of official regulatory sources.

This module deliberately is not a web-search client or crawler.  It can only
request a registry-owned HTTPS search endpoint and a very small number of
same-registry result pages.  Callers supply the deterministic query; no model
selects URLs or sources.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
import socket
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from enum import StrEnum
from typing import Awaitable, Callable, Protocol
from urllib.parse import urlencode, urljoin, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.contracts import AuthorizedContext
from app.modules.regulatory.contracts import RegulatoryEvidence
from app.modules.regulatory.evidence_sufficiency import (
    MissingDomainQueryBuilder,
    QuestionScopeResolution,
)


MAX_SOURCES_PER_REQUEST = 2
MAX_DOCUMENTS_PER_SOURCE = 2
MAX_TOTAL_EVIDENCE = 4
MAX_EXCERPT_CHARS = 1200
MAX_HTTP_RESPONSE_BYTES = 500_000
HTTP_TIMEOUT_SECONDS = 5.0


class SourceRetrievalOutcome(StrEnum):
    """Safe, bounded result classes for one registry-owned source."""

    SUCCESS = "SUCCESS"
    NO_RELEVANT_RESULT = "NO_RELEVANT_RESULT"
    HTTP_NOT_FOUND = "HTTP_NOT_FOUND"
    ACCESS_DENIED = "ACCESS_DENIED"
    TIMEOUT = "TIMEOUT"
    INVALID_CONTENT = "INVALID_CONTENT"
    SECURITY_BLOCKED = "SECURITY_BLOCKED"


class AuthoritativeSourceError(RuntimeError):
    """A controlled per-source retrieval failure with no response content."""

    def __init__(self, message: str, *, outcome: SourceRetrievalOutcome = SourceRetrievalOutcome.INVALID_CONTENT) -> None:
        super().__init__(message)
        self.outcome = outcome


class RetrievalStrategy(StrEnum):
    OFFICIAL_SEARCH_PAGE = "OFFICIAL_SEARCH_PAGE"
    STABLE_DOCUMENT_PAGE = "STABLE_DOCUMENT_PAGE"


class AuthoritativeSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=80)
    organization: str = Field(min_length=1, max_length=255)
    base_domain: str = Field(min_length=1, max_length=255)
    supported_domains: tuple[str, ...] = Field(min_length=1, max_length=6)
    allowed_hosts: tuple[str, ...] = Field(min_length=1, max_length=6)
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.OFFICIAL_SEARCH_PAGE
    search_url: str = Field(min_length=1, max_length=1000)


class AuthoritativeSourceRegistry:
    """Deterministic official-source routing; no user-selected URLs."""

    sources: tuple[AuthoritativeSource, ...] = (
        AuthoritativeSource(
            source_id="cnil",
            organization="CNIL",
            base_domain="cnil.fr",
            supported_domains=("PRIVACY", "AI", "SECURITY_CLOUD"),
            allowed_hosts=("cnil.fr", "www.cnil.fr"),
            search_url="https://www.cnil.fr/fr/recherche?search_api_fulltext={query}",
        ),
        AuthoritativeSource(
            source_id="eur_lex",
            organization="EUR-Lex",
            base_domain="eur-lex.europa.eu",
            supported_domains=("AI", "ENERGY_IOT"),
            allowed_hosts=("eur-lex.europa.eu",),
            retrieval_strategy=RetrievalStrategy.STABLE_DOCUMENT_PAGE,
            # Regulation (EU) 2024/1689: an official ELI document URL, not a
            # guessed search route.  The registry owns this immutable target.
            search_url="https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        ),
        AuthoritativeSource(
            source_id="european_commission_digital",
            organization="European Commission",
            base_domain="digital-strategy.ec.europa.eu",
            supported_domains=("AI",),
            allowed_hosts=("digital-strategy.ec.europa.eu",),
            search_url="https://digital-strategy.ec.europa.eu/en/search?keywords={query}",
        ),
        AuthoritativeSource(
            source_id="anssi",
            organization="ANSSI",
            base_domain="cyber.gouv.fr",
            supported_domains=("SECURITY_CLOUD",),
            allowed_hosts=("cyber.gouv.fr", "www.cyber.gouv.fr"),
            search_url="https://cyber.gouv.fr/recherche?search_api_fulltext={query}",
        ),
        AuthoritativeSource(
            source_id="entreprendre_service_public",
            organization="Entreprendre.Service-Public.fr",
            base_domain="entreprendre.service-public.fr",
            supported_domains=("GENERAL_BUSINESS", "CONTRACTS"),
            allowed_hosts=("entreprendre.service-public.fr",),
            search_url="https://entreprendre.service-public.fr/recherche?keyword={query}",
        ),
        AuthoritativeSource(
            source_id="service_public",
            organization="Service-Public.fr",
            base_domain="service-public.fr",
            supported_domains=("GENERAL_BUSINESS", "CONTRACTS"),
            allowed_hosts=("service-public.fr", "www.service-public.fr"),
            search_url="https://www.service-public.fr/particuliers/recherche?keyword={query}",
        ),
        AuthoritativeSource(
            source_id="ecologie_gouv",
            organization="Ministère de la Transition écologique",
            base_domain="ecologie.gouv.fr",
            supported_domains=("ENERGY_IOT",),
            allowed_hosts=("ecologie.gouv.fr", "www.ecologie.gouv.fr"),
            search_url="https://www.ecologie.gouv.fr/recherche?search_api_fulltext={query}",
        ),
        AuthoritativeSource(
            source_id="ademe",
            organization="ADEME",
            base_domain="ademe.fr",
            supported_domains=("ENERGY_IOT",),
            allowed_hosts=("ademe.fr", "www.ademe.fr"),
            search_url="https://www.ademe.fr/?s={query}",
        ),
    )

    def select(self, domains: list[str], context: AuthorizedContext) -> list[AuthoritativeSource]:
        """Return at most two sources, keeping domain priority deterministic."""

        context_text = " ".join(str(value or "").lower() for value in (
            context.activity, context.sector, context.technology, context.data_context,
            context.target_market, context.location,
        ))
        personal_data = any(term in context_text for term in ("donn", "personnel", "client", "utilisateur"))
        preferred: dict[str, tuple[str, ...]] = {
            "PRIVACY": ("cnil",),
            "AI": ("eur_lex", "european_commission_digital", "cnil") if personal_data else ("eur_lex", "european_commission_digital"),
            "SECURITY_CLOUD": ("anssi", "cnil") if personal_data else ("anssi",),
            "GENERAL_BUSINESS": ("entreprendre_service_public", "service_public"),
            "ENERGY_IOT": ("ecologie_gouv", "ademe", "eur_lex"),
            "CONTRACTS": ("entreprendre_service_public", "service_public"),
        }
        by_id = {source.source_id: source for source in self.sources}
        selected: list[AuthoritativeSource] = []
        for domain in domains:
            selected_before_domain = len(selected)
            for source_id in preferred.get(domain, ()):
                source = by_id.get(source_id)
                if source is None:
                    continue
                if domain not in source.supported_domains or source in selected:
                    continue
                selected.append(source)
                if len(selected) >= MAX_SOURCES_PER_REQUEST:
                    return selected
            # This branch keeps a deliberately narrowed registry testable and
            # lets deployments remove an unavailable primary while retaining
            # another already-approved source for the same domain. It never
            # introduces a source outside the registry.
            if len(selected) != selected_before_domain:
                continue
            for source in sorted(self.sources, key=lambda item: item.source_id):
                if domain not in source.supported_domains or source in selected:
                    continue
                selected.append(source)
                if len(selected) >= MAX_SOURCES_PER_REQUEST:
                    return selected
        return selected


class OfficialHttpResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_code: int = Field(ge=100, le=599)
    headers: dict[str, str] = Field(default_factory=dict)
    text: str = Field(default="", max_length=2_000_000)


class OfficialHttpTransport(Protocol):
    async def get(self, url: str, *, timeout: float) -> OfficialHttpResponse: ...


class HttpxOfficialTransport:
    async def get(self, url: str, *, timeout: float) -> OfficialHttpResponse:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), follow_redirects=False) as client:
            async with client.stream(
                "GET",
                url,
                headers={
                    "Accept": "text/html,application/xhtml+xml;q=0.9",
                    "User-Agent": "RegBridge-authoritative-retrieval/1.0",
                },
            ) as response:
                declared_size = response.headers.get("content-length")
                if declared_size and declared_size.isdigit() and int(declared_size) > MAX_HTTP_RESPONSE_BYTES:
                    raise AuthoritativeSourceError("Authoritative source response exceeded the safe size limit")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > MAX_HTTP_RESPONSE_BYTES:
                        raise AuthoritativeSourceError("Authoritative source response exceeded the safe size limit")
        return OfficialHttpResponse(
            status_code=response.status_code,
            headers={key.lower(): value for key, value in response.headers.items()},
            text=bytes(chunks).decode(response.encoding or "utf-8", errors="replace"),
        )


HostResolver = Callable[[str], Awaitable[list[str]]]


async def _default_host_resolver(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(None, socket.getaddrinfo, host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    return list(dict.fromkeys(item[4][0] for item in rows))


def _host_is_allowed(host: str, source: AuthoritativeSource) -> bool:
    normalized = host.lower().rstrip(".")
    return normalized in source.allowed_hosts


def _validate_url_shape(url: str, source: AuthoritativeSource) -> None:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise AuthoritativeSourceError("Unsupported authoritative source URL", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED)
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise AuthoritativeSourceError("Unsafe authoritative source URL", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED)
    if not _host_is_allowed(parsed.hostname, source):
        raise AuthoritativeSourceError("Unapproved authoritative source host", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED)
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return
    if not address.is_global:
        raise AuthoritativeSourceError("Private authoritative source address", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED)
    # IP literals are not registry hostnames, but keep this explicit so an
    # allowlist can never accidentally permit a private literal.
    raise AuthoritativeSourceError("IP literal authoritative source URL", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED)


async def _validate_resolved_host(url: str, resolver: HostResolver) -> None:
    host = urlsplit(url).hostname
    if not host:
        raise AuthoritativeSourceError("Missing authoritative source host", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED)
    try:
        addresses = await resolver(host)
    except Exception as exc:
        raise AuthoritativeSourceError("Authoritative source host could not be resolved", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED) from exc
    if not addresses:
        raise AuthoritativeSourceError("Authoritative source host could not be resolved", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED)
    for candidate in addresses:
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError as exc:
            raise AuthoritativeSourceError("Invalid authoritative source resolution", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED) from exc
        if not address.is_global:
            raise AuthoritativeSourceError("Private authoritative source address", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED)


def _query_url(source: AuthoritativeSource, query: str) -> str:
    encoded = urlencode({"query": query})
    # Avoid template substitution preserving anything other than the already
    # deterministic query string.  The registry controls the URL template.
    return source.search_url.replace("{query}", encoded.split("=", 1)[1])


def _redirect_target(current_url: str, response: OfficialHttpResponse, source: AuthoritativeSource) -> str | None:
    location = response.headers.get("location")
    if not location:
        return None
    target = urljoin(current_url, location)
    _validate_url_shape(target, source)
    return target


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._link_parts: list[str] = []
        self._active_text_tag: str | None = None
        self._text_parts: list[str] = []
        self._title_active = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self._href = attributes["href"]
            self._link_parts = []
        if tag == "title":
            self._title_active = True
        if tag in {"p", "li", "h1", "h2", "h3"}:
            self._active_text_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            label = " ".join("".join(self._link_parts).split())
            self.links.append((self._href, label))
            self._href = None
            self._link_parts = []
        if tag == "title":
            self._title_active = False
        if tag == self._active_text_tag:
            self._active_text_tag = None

    def handle_data(self, data: str) -> None:
        if self._href:
            self._link_parts.append(data)
        if self._title_active:
            self.title += data
        if self._active_text_tag:
            self._text_parts.append(data)

    @property
    def visible_text(self) -> str:
        return " ".join(" ".join(self._text_parts).split())


def _parse_page(html: str) -> _PageParser:
    parser = _PageParser()
    parser.feed(html[:500_000])
    parser.close()
    return parser


def _normal_terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[a-zA-ZÀ-ÿ0-9]{4,}", query.lower()) if term not in {"pour", "avec", "dans", "france", "votre", "votres"}][:12]


def _bounded_excerpt(text: str, query: str) -> str | None:
    normalized = " ".join(unescape(text).split())
    if not normalized:
        return None
    lower = normalized.lower()
    terms = _normal_terms(query)
    first = min((lower.find(term) for term in terms if lower.find(term) >= 0), default=0)
    start = max(first - 220, 0)
    excerpt = normalized[start:start + MAX_EXCERPT_CHARS]
    return excerpt.strip() or None


def _candidate_urls(search_url: str, parser: _PageParser, source: AuthoritativeSource, query: str) -> list[str]:
    terms = _normal_terms(query)
    candidates: list[tuple[int, str]] = []
    for href, label in parser.links:
        url = urljoin(search_url, href)
        try:
            _validate_url_shape(url, source)
        except AuthoritativeSourceError:
            continue
        score = sum(term in label.lower() or term in url.lower() for term in terms)
        if score:
            candidates.append((score, url))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return list(dict.fromkeys(url for _, url in candidates))[:MAX_DOCUMENTS_PER_SOURCE]


class AuthoritativeRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempted_sources: list[str] = Field(default_factory=list, max_length=MAX_SOURCES_PER_REQUEST)
    succeeded_sources: list[str] = Field(default_factory=list, max_length=MAX_SOURCES_PER_REQUEST)
    failed_sources: list[str] = Field(default_factory=list, max_length=MAX_SOURCES_PER_REQUEST)
    source_outcomes: dict[str, SourceRetrievalOutcome] = Field(default_factory=dict)
    evidence: list[RegulatoryEvidence] = Field(default_factory=list, max_length=MAX_TOTAL_EVIDENCE)


class AuthoritativeSourceRetriever:
    """Fetch a bounded official-source supplement without raw response storage."""

    def __init__(
        self,
        *,
        registry: AuthoritativeSourceRegistry | None = None,
        transport: OfficialHttpTransport | None = None,
        host_resolver: HostResolver | None = None,
        query_builder: MissingDomainQueryBuilder | None = None,
    ) -> None:
        self.registry = registry or AuthoritativeSourceRegistry()
        self.transport = transport or HttpxOfficialTransport()
        self.host_resolver = host_resolver or _default_host_resolver
        self.query_builder = query_builder or MissingDomainQueryBuilder()

    async def retrieve(
        self,
        *,
        question: str,
        domains: list[str],
        scope: QuestionScopeResolution,
        context: AuthorizedContext,
    ) -> AuthoritativeRetrievalResult:
        sources = self.registry.select(domains, context)
        result = AuthoritativeRetrievalResult(attempted_sources=[source.source_id for source in sources])
        evidence: list[RegulatoryEvidence] = []
        for source in sources:
            if len(evidence) >= MAX_TOTAL_EVIDENCE:
                break
            domain = next((value for value in domains if value in source.supported_domains), source.supported_domains[0])
            try:
                query = self.query_builder.build(question, domain, context, scope)
                source_evidence = await self._retrieve_source(source, query, remaining=MAX_TOTAL_EVIDENCE - len(evidence))
            except AuthoritativeSourceError as exc:
                result.failed_sources.append(source.source_id)
                result.source_outcomes[source.source_id] = exc.outcome
                continue
            except (httpx.HTTPError, ValueError):
                result.failed_sources.append(source.source_id)
                result.source_outcomes[source.source_id] = SourceRetrievalOutcome.INVALID_CONTENT
                continue
            result.source_outcomes[source.source_id] = (
                SourceRetrievalOutcome.SUCCESS if source_evidence else SourceRetrievalOutcome.NO_RELEVANT_RESULT
            )
            result.succeeded_sources.append(source.source_id)
            evidence.extend(source_evidence)
        result.evidence = evidence[:MAX_TOTAL_EVIDENCE]
        return result

    async def _fetch(self, url: str, source: AuthoritativeSource) -> OfficialHttpResponse:
        _validate_url_shape(url, source)
        await _validate_resolved_host(url, self.host_resolver)
        try:
            response = await self.transport.get(url, timeout=HTTP_TIMEOUT_SECONDS)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise AuthoritativeSourceError("Authoritative source request timed out", outcome=SourceRetrievalOutcome.TIMEOUT) from exc
        except (httpx.HTTPError, OSError) as exc:
            raise AuthoritativeSourceError("Authoritative source request failed") from exc
        if 300 <= response.status_code < 400:
            target = _redirect_target(url, response, source)
            if target is None:
                raise AuthoritativeSourceError("Authoritative source redirect was invalid", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED)
            await _validate_resolved_host(target, self.host_resolver)
            try:
                response = await self.transport.get(target, timeout=HTTP_TIMEOUT_SECONDS)
            except (TimeoutError, httpx.TimeoutException) as exc:
                raise AuthoritativeSourceError("Authoritative source redirect timed out", outcome=SourceRetrievalOutcome.TIMEOUT) from exc
            except (httpx.HTTPError, OSError) as exc:
                raise AuthoritativeSourceError("Authoritative source redirect failed") from exc
            if 300 <= response.status_code < 400:
                raise AuthoritativeSourceError("Authoritative source exceeded redirect limit", outcome=SourceRetrievalOutcome.SECURITY_BLOCKED)
        if response.status_code == 404:
            raise AuthoritativeSourceError("Authoritative source response was not found", outcome=SourceRetrievalOutcome.HTTP_NOT_FOUND)
        if response.status_code in {401, 403}:
            raise AuthoritativeSourceError("Authoritative source denied automated access", outcome=SourceRetrievalOutcome.ACCESS_DENIED)
        if response.status_code < 200 or response.status_code >= 300:
            raise AuthoritativeSourceError("Authoritative source response was unsuccessful")
        content_type = response.headers.get("content-type", "").lower()
        if not content_type.startswith(("text/html", "application/xhtml+xml")):
            raise AuthoritativeSourceError("Authoritative source returned non-text content", outcome=SourceRetrievalOutcome.INVALID_CONTENT)
        return response

    async def _retrieve_source(self, source: AuthoritativeSource, query: str, *, remaining: int) -> list[RegulatoryEvidence]:
        search_url = _query_url(source, query)
        search_response = await self._fetch(search_url, source)
        if source.retrieval_strategy is RetrievalStrategy.STABLE_DOCUMENT_PAGE:
            page = _parse_page(search_response.text)
            excerpt = _bounded_excerpt(page.visible_text, query)
            if not excerpt:
                return []
            title = " ".join(unescape(page.title).split())[:500] or None
            fingerprint = hashlib.sha256(
                f"{source.source_id}|{search_url}|{title or ''}|{excerpt}".encode("utf-8")
            ).hexdigest()
            return [RegulatoryEvidence(
                point_id=f"live:{source.source_id}:{fingerprint[:32]}",
                rank=1,
                retrieval_score=1.0,
                organization=source.organization,
                source_domain=urlsplit(search_url).hostname,
                url=search_url,
                title=title,
                retrieved_at=datetime.now(UTC),
                provenance_type="LIVE_AUTHORITATIVE",
                content=excerpt,
            )]
        else:
            candidates = _candidate_urls(search_url, _parse_page(search_response.text), source, query)
        collected: list[RegulatoryEvidence] = []
        for url in candidates[: min(MAX_DOCUMENTS_PER_SOURCE, remaining)]:
            response = await self._fetch(url, source)
            page = _parse_page(response.text)
            excerpt = _bounded_excerpt(page.visible_text, query)
            if not excerpt:
                continue
            title = " ".join(unescape(page.title).split())[:500] or None
            fingerprint = hashlib.sha256(f"{source.source_id}|{url}|{title or ''}|{excerpt}".encode("utf-8")).hexdigest()
            collected.append(RegulatoryEvidence(
                point_id=f"live:{source.source_id}:{fingerprint[:32]}",
                rank=len(collected) + 1,
                retrieval_score=1.0,
                organization=source.organization,
                source_domain=urlsplit(url).hostname,
                url=url,
                title=title,
                retrieved_at=datetime.now(UTC),
                provenance_type="LIVE_AUTHORITATIVE",
                content=excerpt,
            ))
        return collected
