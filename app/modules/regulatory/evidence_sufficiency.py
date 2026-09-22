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


class QuestionScope(StrEnum):
    GENERAL_INFORMATION = "GENERAL_INFORMATION"
    GENERAL_OBLIGATIONS = "GENERAL_OBLIGATIONS"
    PROJECT_SPECIFIC = "PROJECT_SPECIFIC"
    SECTOR_SPECIFIC = "SECTOR_SPECIFIC"
    CLASSIFICATION_SPECIFIC = "CLASSIFICATION_SPECIFIC"


class QuestionScopeResolution(BaseModel):
    """Small, deterministic description of the answer specificity requested."""

    model_config = ConfigDict(extra="forbid")

    scope: QuestionScope
    matched_signals: list[str] = Field(default_factory=list, max_length=12)


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
    question_scope: QuestionScope
    scope_matched_signals: list[str] = Field(default_factory=list, max_length=12)
    scope_supported: bool = False
    scope_unsupported_domains: list[str] = Field(default_factory=list, max_length=6)
    scope_support_reasons: list[str] = Field(default_factory=list, max_length=6)
    resolution_source: ResolutionSource
    matched_signals: list[str] = Field(default_factory=list, max_length=12)
    needs_clarification: bool = False


_DOMAINS = ("GENERAL_BUSINESS", "PRIVACY", "AI", "SECURITY_CLOUD", "ENERGY_IOT", "CONTRACTS")
_QUESTION_SIGNALS = {
    "PRIVACY": ("rgpd", "gdpr", "donnees personnelles", "protection des donnees", "cnil", "traitement de donnees", "vie privee"),
    "AI": ("intelligence artificielle", "ai act", "ia", "systeme d ia", "modele d ia", "machine learning", "ai/ml"),
    "SECURITY_CLOUD": ("cybersecurite", "securite informatique", "cloud", "hebergement", "hebergeur", "anssi", "saas"),
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
_OBLIGATION_TERMS = ("obligation", "obligations", "doit", "doivent", "exige", "requis", "obligatoire", "interdit", "tenu", "responsable", "soumis")
_APPLICABILITY_TERMS = ("s applique", "applicable", "soumis", "condition", "conditions", "lorsque", "si ", "dans le cas", "responsable", "tenu")
_CONTEXTUAL_APPLICABILITY_TERMS = ("s applique", "soumis", "condition", "conditions", "lorsque", "si ", "dans le cas", "responsable", "tenu")
_DEFINITION_TERMS = ("reglement", "cadre", "protection", "definition", "definit", "concerne", "vise")
_CLASSIFICATION_TERMS = ("classification", "classer", "categorie", "niveau de risque", "haut risque", "risque", "regime")
_CLASSIFICATION_CRITERIA_TERMS = ("critere", "criteres", "annexe", "finalite", "destine", "usage", "utilise", "deploie", "lorsque", "si ")
_SECTOR_TERMS = ("compteur", "compteurs", "iot", "capteur", "capteurs", "energie", "energetique", "linky", "gazpar")
_SECTOR_BINDING_TERMS = ("exploitant", "operateur", "fournisseur", "fabricant", "mise sur le marche", "installation", "deploiement")
_PROJECT_TERMS = {
    "PRIVACY": ("traitement", "donnees personnelles", "responsable"),
    "AI": ("systeme", "intelligence artificielle", "modele", "algorithme"),
    "SECURITY_CLOUD": ("saas", "cloud", "hebergement", "service numerique"),
    "ENERGY_IOT": ("compteur", "iot", "capteur", "energie"),
    "GENERAL_BUSINESS": ("entreprise", "societe", "activite"),
    "CONTRACTS": ("contrat", "cgv", "cgu", "clause"),
}
_LABELS = {
    "GENERAL_BUSINESS": "création et gestion de l’entreprise",
    "PRIVACY": "protection des données personnelles",
    "AI": "intelligence artificielle",
    "SECURITY_CLOUD": "sécurité et services cloud",
    "ENERGY_IOT": "énergie et objets connectés",
    "CONTRACTS": "contrats",
}

# Broadening a regulatory request with private project facts is a separate
# decision from identifying a regulatory topic in the question.  Only an
# unambiguous project-relative phrase may make that enrichment decision.
_EXPLICIT_PROJECT_REFERENCES = (
    "ce projet",
    "mon projet",
    "notre projet",
    "ma plateforme",
    "mon saas",
    "dans mon cas",
)


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

    _SCOPE_TERMS = {
        QuestionScope.PROJECT_SPECIFIC: {
            "SECURITY_CLOUD": ("obligations cybersecurite applicables", "saas cloud hebergement donnees entreprise france"),
            "PRIVACY": ("obligations applicables traitement donnees entreprise france",),
            "AI": ("obligations applicables systeme ia entreprise france",),
            "ENERGY_IOT": ("obligations applicables compteurs iot energie entreprise france",),
        },
        QuestionScope.SECTOR_SPECIFIC: {
            "ENERGY_IOT": ("obligations sectorielles reglementation compteurs iot energetiques dispositifs mesure energie france",),
        },
        QuestionScope.CLASSIFICATION_SPECIFIC: {
            "AI": ("ai act classification niveau risque criteres applicabilite systeme ia entreprise france union europeenne",),
        },
    }

    def build(
        self,
        question: str,
        missing_domain: str,
        context: AuthorizedContext,
        scope: QuestionScopeResolution | None = None,
    ) -> str:
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
        scope_terms = self._SCOPE_TERMS.get(scope.scope if scope else QuestionScope.GENERAL_OBLIGATIONS, {}).get(missing_domain, ())
        return " ".join(dict.fromkeys((subject, *self._CANONICAL_TERMS[missing_domain], *scope_terms, *contextual)))[:500]


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
        # “SaaS” supplies a cloud-domain topic only for an otherwise broad
        # generic request. When a more specific domain is explicit, it is a
        # business descriptor rather than an additional regulatory domain.
        if len(domains) > 1 and explicit["SECURITY_CLOUD"] == ["saas"]:
            domains.remove("SECURITY_CLOUD")
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
        asks_about_regulation = bool(re.search(r"(?<![a-z0-9])(obligation|reglement|regle|conformit)[a-z]*(?![a-z0-9])", question))
        return asks_about_regulation and any(_matches(question, reference) for reference in _EXPLICIT_PROJECT_REFERENCES)

    @staticmethod
    def _ordered(values: list[str]) -> list[str]:
        return [domain for domain in _DOMAINS if domain in values]


class QuestionScopeResolver:
    """Classify only the specificity requested by a question; never use an LLM."""

    _GENERAL_INFORMATION = ("what is", "qu est ce que", "definition", "signifie")
    _SECTOR_SPECIFIC = ("sectoriel", "sectorielle", "specifique au secteur", "specifiques au secteur", "specifique a", "specifiques a", "pour mes compteurs", "pour mes capteurs")
    _CLASSIFICATION_SPECIFIC = ("classification", "classer", "niveau de risque", "haut risque", "quelle categorie", "precisement mon systeme", "quel regime", "est ce que mon systeme est")
    _PROJECT_SPECIFIC = ("mon projet", "mon saas", "ma plateforme", "mon systeme", "dans mon cas", "s applique a", "s appliquent a")
    _OBLIGATIONS = ("obligation", "obligations", "exigence", "exigences", "reglement", "regles", "conformite", "dois je")

    def resolve(self, question: str) -> QuestionScopeResolution:
        normalized = _normal(question)
        for scope, signals in (
            (QuestionScope.CLASSIFICATION_SPECIFIC, self._CLASSIFICATION_SPECIFIC),
            (QuestionScope.SECTOR_SPECIFIC, self._SECTOR_SPECIFIC),
            (QuestionScope.PROJECT_SPECIFIC, self._PROJECT_SPECIFIC),
            (QuestionScope.GENERAL_INFORMATION, self._GENERAL_INFORMATION),
        ):
            matched = _matched_signals(normalized, signals)
            if matched:
                return QuestionScopeResolution(scope=scope, matched_signals=[f"question_scope:{signal}" for signal in matched])
        matched = _matched_signals(normalized, self._OBLIGATIONS)
        if matched:
            return QuestionScopeResolution(scope=QuestionScope.GENERAL_OBLIGATIONS, matched_signals=[f"question_scope:{signal}" for signal in matched])
        return QuestionScopeResolution(scope=QuestionScope.GENERAL_INFORMATION, matched_signals=["question_scope:default_general_information"])


class EvidenceSufficiencyEvaluator:
    """Assess retrieved evidence against an already-resolved domain scope."""

    def evaluate(
        self,
        resolution: RequiredDomainResolution,
        evidence: list[RegulatoryEvidence],
        scope: QuestionScopeResolution | None = None,
        context: AuthorizedContext | None = None,
    ) -> EvidenceAssessment:
        scope = scope or QuestionScopeResolution(
            scope=QuestionScope.GENERAL_OBLIGATIONS,
            matched_signals=["question_scope:compatibility_general_obligations"],
        )
        required = resolution.required_domains
        matches: dict[str, list[RegulatoryEvidence]] = {domain: [] for domain in required}
        for item in evidence:
            text = _normal(" ".join((item.organization, item.source_domain or "", item.content)))
            substantive = any(_matches(text, signal) for signal in _SUBSTANTIVE_TERMS)
            conceptual = any(_matches(text, signal) for signal in _DEFINITION_TERMS)
            for domain in required:
                topic = domain == "GENERAL_BUSINESS" or any(_matches(text, signal) for signal in _EVIDENCE_TERMS[domain])
                useful = (conceptual or substantive) if scope.scope == QuestionScope.GENERAL_INFORMATION else substantive
                if topic and useful and (domain == "GENERAL_BUSINESS" or len(item.content.split()) >= 8):
                    matches[domain].append(item)
        covered = [domain for domain in required if matches[domain]]
        missing = [domain for domain in required if domain not in covered]
        useful = {item.point_id for items in matches.values() for item in items}
        scope_supported, scope_unsupported_domains, scope_reasons = self._scope_supported(scope, matches, context)
        status = (
            EvidenceStatus.INSUFFICIENT
            if not evidence or not covered
            else EvidenceStatus.PARTIAL
            if missing or not scope_supported
            else EvidenceStatus.SUFFICIENT
        )
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
            question_scope=scope.scope, scope_matched_signals=scope.matched_signals,
            scope_supported=scope_supported, scope_unsupported_domains=scope_unsupported_domains, scope_support_reasons=scope_reasons,
            matched_signals=resolution.matched_signals, needs_clarification=resolution.needs_clarification,
        )

    @staticmethod
    def _scope_supported(
        scope: QuestionScopeResolution,
        matches: dict[str, list[RegulatoryEvidence]],
        context: AuthorizedContext | None,
    ) -> tuple[bool, list[str], list[str]]:
        if not matches or not any(matches.values()):
            return False, [], ["scope_not_supported; no_useful_required_domain_evidence"]
        supported_domains = [
            domain for domain, items in matches.items()
            if EvidenceSufficiencyEvaluator._domain_supports_scope(scope.scope, domain, items, context)
        ]
        required = list(matches)
        if required and set(supported_domains) == set(required):
            return True, [], [f"scope_supported; scope={scope.scope.value}; supported_domains={', '.join(supported_domains)}"]
        missing = [domain for domain in required if domain not in supported_domains]
        scope_gaps = [domain for domain in missing if matches[domain]]
        return False, scope_gaps, [f"scope_not_supported; scope={scope.scope.value}; insufficient_specificity_domains={', '.join(missing)}"]

    @staticmethod
    def _domain_supports_scope(
        scope: QuestionScope,
        domain: str,
        items: list[RegulatoryEvidence],
        context: AuthorizedContext | None,
    ) -> bool:
        texts = [_normal(" ".join((item.organization, item.source_domain or "", item.content))) for item in items]
        if scope == QuestionScope.GENERAL_INFORMATION:
            # Topic coverage was already established before this scope check.
            # A source can explain a concept through concrete obligations as
            # well as an explicit dictionary-style definition.
            return bool(texts)
        if scope == QuestionScope.GENERAL_OBLIGATIONS:
            return any(any(_matches(text, term) for term in _OBLIGATION_TERMS) for text in texts)
        if scope == QuestionScope.CLASSIFICATION_SPECIFIC:
            return any(
                any(_matches(text, term) for term in _OBLIGATION_TERMS)
                and any(_matches(text, term) for term in _CLASSIFICATION_TERMS)
                and any(_matches(text, term) for term in _CLASSIFICATION_CRITERIA_TERMS)
                and any(_matches(text, term) for term in _CONTEXTUAL_APPLICABILITY_TERMS)
                and EvidenceSufficiencyEvaluator._has_confirmed_context_match(text, domain, context)
                for text in texts
            )
        if scope == QuestionScope.SECTOR_SPECIFIC:
            return any(
                any(_matches(text, term) for term in _OBLIGATION_TERMS)
                and any(_matches(text, term) for term in _CONTEXTUAL_APPLICABILITY_TERMS)
                and any(_matches(text, term) for term in _SECTOR_BINDING_TERMS)
                and sum(_matches(text, term) for term in _SECTOR_TERMS) >= 2
                and EvidenceSufficiencyEvaluator._has_confirmed_context_match(text, domain, context)
                for text in texts
            )
        return any(
            any(_matches(text, term) for term in _OBLIGATION_TERMS)
            and any(_matches(text, term) for term in _CONTEXTUAL_APPLICABILITY_TERMS)
            and EvidenceSufficiencyEvaluator._has_confirmed_context_match(text, domain, context)
            for text in texts
        )

    @staticmethod
    def _has_confirmed_context_match(text: str, domain: str, context: AuthorizedContext | None) -> bool:
        """Require a bounded project characteristic without serialising it."""

        if context is None:
            return False
        context_text = _normal(" ".join(str(value or "") for value in (
            context.activity, context.sector, context.technology, context.data_context,
            context.target_market, context.location,
        )))
        return any(
            _matches(text, term) and _matches(context_text, term)
            for term in _PROJECT_TERMS.get(domain, ())
        )


def public_domain_labels(domains: list[str]) -> list[str]:
    return [_LABELS.get(domain, domain) for domain in domains]
