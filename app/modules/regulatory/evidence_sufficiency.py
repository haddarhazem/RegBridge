"""Deterministic, inspectable regulatory-domain resolution and coverage checks."""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.contracts import AuthorizedContext
from app.modules.ai.pipeline_types import EvidenceStatus
from app.modules.regulatory.contracts import RegulatoryEvidence


class ResolutionSource(StrEnum):
    QUESTION_EXPLICIT = "QUESTION_EXPLICIT"
    PROJECT_CONTEXT_BROAD_QUESTION = "PROJECT_CONTEXT_BROAD_QUESTION"
    UNRESOLVED = "UNRESOLVED"


class RequiredDomainResolution(BaseModel):
    """A question-scoped, trace-safe domain decision before retrieval."""

    model_config = ConfigDict(extra="forbid")

    required_domains: list[str] = Field(default_factory=list, max_length=6)
    resolution_source: ResolutionSource
    matched_signals: list[str] = Field(default_factory=list, max_length=12)
    needs_clarification: bool = False


class EvidenceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_domains: list[str] = Field(default_factory=list, max_length=6)
    covered_domains: list[str] = Field(default_factory=list, max_length=6)
    missing_domains: list[str] = Field(default_factory=list, max_length=6)
    # One initial top-k retrieval plus one bounded top-k retrieval for each
    # taxonomy domain can be merged before the same evaluator runs again.
    useful_evidence_count: int = Field(ge=0, le=35)
    total_evidence_count: int = Field(ge=0, le=35)
    status: EvidenceStatus
    domain_reasons: dict[str, str] = Field(default_factory=dict, max_length=6)
    resolution_source: ResolutionSource
    matched_signals: list[str] = Field(default_factory=list, max_length=12)
    needs_clarification: bool = False


_DOMAINS = ("GENERAL_BUSINESS", "PRIVACY", "AI", "SECURITY_CLOUD", "ENERGY_IOT", "CONTRACTS")
_QUESTION_SIGNALS = {
    "PRIVACY": ("rgpd", "gdpr", "donnees personnelles", "protection des donnees", "cnil", "traitement de donnees", "vie privee"),
    "AI": ("intelligence artificielle", "ai act", "ia", "systeme d ia", "modele d ia", "machine learning", "ai/ml"),
    "SECURITY_CLOUD": ("cybersecurite", "securite informatique", "cloud", "hebergement", "hebergeur", "anssi"),
    "ENERGY_IOT": ("energie", "energetique", "compteur intelligent", "iot", "capteur", "consommation energetique"),
    "CONTRACTS": ("contrat", "cgv", "cgu", "nda", "accord", "clause", "obligation contractuelle"),
    "GENERAL_BUSINESS": ("creation d entreprise", "immatriculation", "societe", "formalites", "guichet unique", "forme juridique", "lancer mon entreprise"),
}
_CONTEXT_SIGNALS = {
    "PRIVACY": ("donnees personnelles", "traitement", "coordonnees professionnelles"),
    "AI": ("intelligence artificielle", "ai/ml", "machine learning", "modele d ia"),
    "SECURITY_CLOUD": ("saas", "cloud", "hebergement", "hebergeur"),
    "ENERGY_IOT": ("energie", "energetique", "compteur", "iot", "capteur", "consommation"),
    "CONTRACTS": ("contrat", "cgv", "cgu", "nda", "clause"),
}
_EVIDENCE_TERMS = {
    **_QUESTION_SIGNALS,
    "SECURITY_CLOUD": ("cybersecurite", "securite", "cloud", "hebergement", "anssi", "incident", "authentification"),
}
_SUBSTANTIVE_TERMS = ("obligation", "obligations", "doit", "doivent", "exige", "requis", "applicable", "responsable", "mesure", "declaration", "conformite", "protection", "droit", "droits", "regle", "regles", "officiel", "reglementaire", "reglementaires")
_LABELS = {
    "GENERAL_BUSINESS": "création et gestion de l’entreprise",
    "PRIVACY": "protection des données personnelles",
    "AI": "intelligence artificielle",
    "SECURITY_CLOUD": "sécurité et services cloud",
    "ENERGY_IOT": "énergie et objets connectés",
    "CONTRACTS": "contrats",
}


class MissingDomainQueryBuilder:
    """Build one small deterministic Qdrant query for a missing domain.

    The builder deliberately reuses the resolver taxonomy.  It never invokes a
    provider and it only adds generic, confirmed contextual vocabulary rather
    than serialising the project description or private material.
    """

    _CANONICAL_TERMS = {
        "PRIVACY": ("obligations", "rgpd", "protection des donnees personnelles", "traitement des donnees", "france"),
        "AI": ("obligations", "intelligence artificielle", "ai act", "systeme ia", "machine learning", "france"),
        "SECURITY_CLOUD": ("obligations", "cybersecurite", "securite cloud", "hebergement saas", "france"),
        "ENERGY_IOT": ("obligations", "reglementation energie", "iot", "compteurs intelligents", "entreprise france"),
        "GENERAL_BUSINESS": ("obligations", "creation entreprise", "immatriculation", "formalites societe", "france"),
        "CONTRACTS": ("obligations", "contractuelles", "contrats", "cgv cgu", "entreprise france"),
    }

    _CONTEXT_TERMS = {
        "PRIVACY": ("donnees personnelles", "coordonnees professionnelles", "traitement"),
        "AI": ("intelligence artificielle", "machine learning", "ai/ml"),
        "SECURITY_CLOUD": ("saas", "cloud", "hebergement"),
        "ENERGY_IOT": ("energie", "energetique", "iot", "compteur", "capteur"),
        "CONTRACTS": ("contrat", "cgv", "cgu", "nda", "clause"),
        "GENERAL_BUSINESS": (),
    }

    def build(self, question: str, missing_domain: str, context: AuthorizedContext) -> str:
        if missing_domain not in self._CANONICAL_TERMS:
            raise ValueError(f"Unsupported regulatory domain: {missing_domain}")
        # Keep the user's subject while bounding the retrieval string.  This
        # query is transient; callers must not put it in a trace payload.
        subject = " ".join(question.split())[:240]
        context_text = _normal(" ".join(str(value or "") for value in (
            context.activity, context.sector, context.technology, context.data_context,
            context.target_market, context.location,
        )))
        contextual = [
            term for term in self._CONTEXT_TERMS[missing_domain]
            if _matches(context_text, term)
        ][:2]
        return " ".join(dict.fromkeys((subject, *self._CANONICAL_TERMS[missing_domain], *contextual)))


def _normal(value: str | None) -> str:
    raw = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in raw.lower() if not unicodedata.combining(char))


def _matches(value: str, signal: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(signal)}(?![a-z0-9])", value))


def _matched_signals(value: str, signals: tuple[str, ...]) -> list[str]:
    return [signal for signal in signals if _matches(value, signal)]


class RequiredDomainResolver:
    """Resolve only what the question explicitly asks, or a broad project ask."""

    def resolve(self, question: str, context: AuthorizedContext) -> RequiredDomainResolution:
        normalized = _normal(question)
        explicit = {domain: _matched_signals(normalized, signals) for domain, signals in _QUESTION_SIGNALS.items()}
        domains = [domain for domain, signals in explicit.items() if signals]
        if domains:
            ordered = self._ordered(domains)
            return RequiredDomainResolution(
                required_domains=ordered,
                resolution_source=ResolutionSource.QUESTION_EXPLICIT,
                matched_signals=[f"question:{signal}" for domain in ordered for signal in explicit[domain]],
            )
        if not self._is_broad_project_question(normalized):
            return RequiredDomainResolution(resolution_source=ResolutionSource.UNRESOLVED, needs_clarification=True)
        context_text = " ".join(_normal(value) for value in (
            context.activity, context.sector, context.technology, context.data_context,
            context.target_market, context.location,
            *(str(fact.get("value", "")) for fact in context.facts),
        ))
        domains = ["GENERAL_BUSINESS"]
        signals = ["question:broad_regulatory_project"]
        if context.country_code == "FR":
            signals.append("context:country_france")
        for domain, values in _CONTEXT_SIGNALS.items():
            matches = _matched_signals(context_text, values)
            if matches:
                domains.append(domain)
                signals.extend(f"context:{signal}" for signal in matches)
        return RequiredDomainResolution(
            required_domains=self._ordered(domains),
            resolution_source=ResolutionSource.PROJECT_CONTEXT_BROAD_QUESTION,
            matched_signals=signals,
        )

    @staticmethod
    def _is_broad_project_question(question: str) -> bool:
        return bool(re.search(r"(?<![a-z0-9])(obligation|reglement|regle|conformit)[a-z]*(?![a-z0-9])", question)) and any(
            _matches(question, signal) for signal in ("projet", "entreprise", "france", "respecter", "concerne")
        )

    @staticmethod
    def _ordered(values: list[str]) -> list[str]:
        return [domain for domain in _DOMAINS if domain in values]


class EvidenceSufficiencyEvaluator:
    """Assess retrieved evidence against an already-resolved domain scope."""

    def evaluate(self, resolution: RequiredDomainResolution, evidence: list[RegulatoryEvidence]) -> EvidenceAssessment:
        required = resolution.required_domains
        matches: dict[str, list[RegulatoryEvidence]] = {domain: [] for domain in required}
        for item in evidence:
            text = _normal(" ".join((item.organization, item.source_domain or "", item.content)))
            substantive = any(_matches(text, signal) for signal in _SUBSTANTIVE_TERMS)
            for domain in required:
                topic = domain == "GENERAL_BUSINESS" or any(_matches(text, signal) for signal in _EVIDENCE_TERMS[domain])
                if topic and substantive and (domain == "GENERAL_BUSINESS" or len(item.content.split()) >= 8):
                    matches[domain].append(item)
        covered = [domain for domain in required if matches[domain]]
        missing = [domain for domain in required if domain not in covered]
        useful = {item.point_id for items in matches.values() for item in items}
        status = EvidenceStatus.INSUFFICIENT if not evidence or not covered else EvidenceStatus.PARTIAL if missing else EvidenceStatus.SUFFICIENT
        reasons = {
            domain: (
                f"covered; matched_chunks={len(matches[domain])}; organizations={', '.join(dict.fromkeys(item.organization for item in matches[domain]))}"
                if matches[domain] else "missing; matched_chunks=0"
            ) for domain in required
        }
        return EvidenceAssessment(
            required_domains=required, covered_domains=covered, missing_domains=missing,
            useful_evidence_count=len(useful), total_evidence_count=len(evidence), status=status,
            domain_reasons=reasons, resolution_source=resolution.resolution_source,
            matched_signals=resolution.matched_signals, needs_clarification=resolution.needs_clarification,
        )


def public_domain_labels(domains: list[str]) -> list[str]:
    return [_LABELS.get(domain, domain) for domain in domains]
