"""Deterministic, inspectable coverage checks for retrieved regulation."""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.contracts import AuthorizedContext
from app.modules.ai.pipeline_types import EvidenceStatus
from app.modules.regulatory.contracts import RegulatoryEvidence


class EvidenceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_domains: list[str] = Field(default_factory=list, max_length=6)
    covered_domains: list[str] = Field(default_factory=list, max_length=6)
    missing_domains: list[str] = Field(default_factory=list, max_length=6)
    useful_evidence_count: int = Field(ge=0, le=5)
    total_evidence_count: int = Field(ge=0, le=5)
    status: EvidenceStatus
    domain_reasons: dict[str, str] = Field(default_factory=dict, max_length=6)


_DOMAINS = ("GENERAL_BUSINESS", "PRIVACY", "AI", "SECURITY_CLOUD", "ENERGY_IOT", "CONTRACTS")
_DOMAIN_TERMS = {
    "PRIVACY": ("rgpd", "donnee personnelle", "donnees personnelles", "traitement", "cnil", "privacy"),
    "AI": ("intelligence artificielle", "ai act", "systeme d ia", "systemes d ia", "ia generative", "machine learning", "ai/ml"),
    "SECURITY_CLOUD": ("cybersecurite", "securite", "cloud", "hebergement", "anssi", "incident", "authentification"),
    "ENERGY_IOT": ("energie", "energetique", "compteur", "iot", "consommation", "capteur"),
    "CONTRACTS": ("contrat", "cgv", "conditions generales", "clause", "contractuel"),
    "GENERAL_BUSINESS": ("immatriculation", "societe", "entreprise", "guichet unique", "creation d entreprise", "formalites"),
}
_SUBSTANTIVE_TERMS = ("obligation", "doit", "doivent", "exige", "requis", "applicable", "responsable", "mesure", "declaration", "conformite", "protection", "droit", "regle", "officiel", "reglementaire")
_LABELS = {
    "GENERAL_BUSINESS": "création et gestion de l’entreprise",
    "PRIVACY": "protection des données personnelles",
    "AI": "intelligence artificielle",
    "SECURITY_CLOUD": "sécurité et services cloud",
    "ENERGY_IOT": "énergie et objets connectés",
    "CONTRACTS": "contrats",
}


def _normal(value: str | None) -> str:
    raw = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in raw.lower() if not unicodedata.combining(char))


def _contains(value: str, terms: tuple[str, ...]) -> bool:
    return any(term in value for term in terms)


class EvidenceSufficiencyEvaluator:
    """Small heuristic, intentionally explicit and non-probabilistic."""

    def required_domains(self, question: str, context: AuthorizedContext) -> list[str]:
        normalized = _normal(question)
        direct = [domain for domain, terms in _DOMAIN_TERMS.items() if _contains(normalized, terms)]
        if direct:
            return self._ordered(direct)

        broad = any(marker in normalized for marker in ("principales obligations", "obligations reglementaires", "mon projet", "lancer", "demarrer"))
        if not broad:
            return ["GENERAL_BUSINESS"]
        trusted = " ".join(_normal(value) for value in (
            context.activity, context.sector, context.technology, context.data_context, context.target_market, context.location,
            *(str(fact.get("value", "")) for fact in context.facts),
        ))
        domains = ["GENERAL_BUSINESS"]
        if _contains(trusted, _DOMAIN_TERMS["PRIVACY"]): domains.append("PRIVACY")
        if _contains(trusted, _DOMAIN_TERMS["AI"]): domains.append("AI")
        if _contains(trusted, _DOMAIN_TERMS["SECURITY_CLOUD"]): domains.append("SECURITY_CLOUD")
        if _contains(trusted, _DOMAIN_TERMS["ENERGY_IOT"]): domains.append("ENERGY_IOT")
        if _contains(trusted, _DOMAIN_TERMS["CONTRACTS"]): domains.append("CONTRACTS")
        return self._ordered(domains)

    def evaluate(self, question: str, context: AuthorizedContext, evidence: list[RegulatoryEvidence]) -> EvidenceAssessment:
        required = self.required_domains(question, context)
        matches: dict[str, list[RegulatoryEvidence]] = {domain: [] for domain in required}
        question_terms = tuple(token for token in re.findall(r"[a-z]{4,}", _normal(question)) if token not in {"quelles", "quelle", "projet", "pourquoi", "dois", "doivent"})
        for item in evidence:
            text = _normal(" ".join((item.organization, item.source_domain or "", item.content)))
            substantive = _contains(text, _SUBSTANTIVE_TERMS)
            for domain in required:
                topic = domain == "GENERAL_BUSINESS" or _contains(text, _DOMAIN_TERMS[domain])
                # A long factual chunk may use a question word rather than a second domain synonym.
                question_link = any(token in text for token in question_terms)
                if topic and substantive and (domain == "GENERAL_BUSINESS" or question_link or len(item.content.split()) >= 12):
                    matches[domain].append(item)
        covered = [domain for domain in required if matches[domain]]
        missing = [domain for domain in required if domain not in covered]
        useful = {item.point_id for items in matches.values() for item in items}
        if not evidence or not covered:
            status = EvidenceStatus.INSUFFICIENT
        elif missing:
            status = EvidenceStatus.PARTIAL
        else:
            status = EvidenceStatus.SUFFICIENT
        reasons = {
            domain: (
                f"covered; matched_chunks={len(matches[domain])}; organizations={', '.join(dict.fromkeys(item.organization for item in matches[domain]))}"
                if matches[domain] else "missing; matched_chunks=0"
            )
            for domain in required
        }
        return EvidenceAssessment(
            required_domains=required,
            covered_domains=covered,
            missing_domains=missing,
            useful_evidence_count=len(useful),
            total_evidence_count=len(evidence),
            status=status,
            domain_reasons=reasons,
        )

    @staticmethod
    def _ordered(values: list[str]) -> list[str]:
        return [domain for domain in _DOMAINS if domain in values]


def public_domain_labels(domains: list[str]) -> list[str]:
    return [_LABELS.get(domain, domain) for domain in domains]
