"""Typed project-fact contracts and conservative deterministic extraction."""

from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FactDomain = Literal["activity", "sector", "technology", "data", "market", "location"]
FactOrigin = Literal["inferred", "user_declared"]
FactStatus = Literal["pending_confirmation", "confirmed", "corrected", "deleted"]
FactUncertainty = Literal["high", "medium", "low"]


class FactProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_field: str = Field(min_length=1, max_length=80)
    excerpt: str = Field(min_length=1, max_length=300)
    rule: str | None = Field(default=None, max_length=120)
    correction: str | None = Field(default=None, max_length=300)


class ProjectFactDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID
    domain: FactDomain
    value: str = Field(min_length=1, max_length=500)
    origin: FactOrigin
    status: FactStatus
    provenance: FactProvenance
    uncertainty: FactUncertainty


def _norm(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c))


def _negated(text: str, term: str) -> bool:
    index = text.find(term)
    if index < 0:
        return False
    return bool(re.search(r"(?:pas|aucun|aucune|sans|ne contient)\s+(?:de|d'|d)?\s*$", text[max(0, index - 35):index]))


def _excerpt(description: str, normalized: str) -> str:
    source = _norm(description)
    start = source.find(_norm(normalized))
    if start < 0:
        return normalized[:300]
    positions: list[int] = []
    for index, char in enumerate(description):
        positions.extend([index] * len(_norm(char)))
    end = min(len(positions) - 1, start + len(_norm(normalized)) - 1)
    return description[positions[start] : positions[end] + 1][:300]


def _fact(domain: FactDomain, value: str, excerpt: str, rule: str, uncertainty: FactUncertainty = "high") -> dict:
    return {"domain": domain, "value": value, "origin": "inferred", "status": "pending_confirmation", "provenance": {"source_field": "description", "excerpt": excerpt, "rule": rule}, "uncertainty": uncertainty}


def extract_project_facts(description: str) -> list[dict]:
    text = _norm(description)
    facts: list[dict] = []
    activity_terms = [
        ("boulangerie artisanale", "boulangerie artisanale"), ("boutique e-commerce", "boutique e-commerce"),
        ("logiciel saas de facturation", "logiciel SaaS de facturation"), ("application d'intelligence artificielle", "application d'intelligence artificielle"),
        ("service de paiement en ligne", "service de paiement en ligne"), ("plateforme numerique de sante", "plateforme numérique de santé"),
        ("capteur connecte", "capteur connecté"), ("service de transport et logistique", "service de transport et logistique"),
        ("plateforme web de formation", "plateforme web de formation"), ("gestion energetique", "gestion énergétique"),
        ("conseil en organisation", "conseil en organisation"), ("programme de fidelite", "programme de fidélité"),
        ("fabrication de meubles artisanaux", "fabrication de meubles artisanaux"), ("application de prise de rendez-vous", "application de prise de rendez-vous"),
        ("logiciel de gestion documentaire", "logiciel de gestion documentaire"), ("service d'accompagnement scolaire en ligne", "service d'accompagnement scolaire en ligne"),
    ]
    for term, value in activity_terms:
        if term in text:
            facts.append(_fact("activity", value, _excerpt(description, term), "activity-lexical"))
            break

    sector_terms = [
        (("pain", "patisserie"), "alimentation"), (("logiciel b2b", "entreprises clientes"), "logiciel B2B"),
        (("medecin", "patient", "medical", "sante"), "santé"), (("fintech", "paiement"), "fintech"),
        (("industri", "usine", "capteur"), "industrie"), (("transport", "logistique"), "transport et logistique"),
        (("formation", "education", "etudiant", "scolaire"), "éducation"), (("energetique", "energie"), "énergie"),
        (("pme", "conseil"), "services B2B"), (("artisan",), "artisanat"), (("secteur public",), "secteur public"),
    ]
    for terms, value in sector_terms:
        term = next((term for term in terms if term in text), None)
        if term and not (value == "santé" and ("sans traitement de donnees de sante" in text or "pas de donnees medicales" in text)):
            facts.append(_fact("sector", value, _excerpt(description, term), "sector-lexical"))
            break

    technology_terms = [("intelligence artificielle", "intelligence artificielle"), ("saas", "SaaS"), ("e-commerce", "e-commerce"), ("marketplace", "marketplace"), ("capteur connecte", "capteur connecté"), ("iot", "IoT"), ("application", "application"), ("plateforme numerique", "plateforme numérique"), ("plateforme web", "plateforme web"), ("gestion energetique", "gestion énergétique"), ("paiement en ligne", "paiement en ligne"), ("logiciel", "logiciel")]
    for term, value in technology_terms:
        if term in text and not _negated(text, term):
            facts.append(_fact("technology", value, _excerpt(description, term), "technology-lexical"))
            break
    if _negated(text, "intelligence artificielle"):
        facts.append(_fact("technology", "pas d'intelligence artificielle", _excerpt(description, "intelligence artificielle"), "technology-negation"))
    if _negated(text, "logiciel"):
        facts.append(_fact("technology", "aucun logiciel", _excerpt(description, "logiciel"), "technology-negation"))

    if "donnees personnelles" in text and "clients" in text:
        facts.append(_fact("data", "données personnelles des clients", _excerpt(description, "données personnelles"), "data-explicit"))
    elif "donnees de sante" in text and "patient" in text:
        facts.append(_fact("data", "données de santé des patients", _excerpt(description, "données de santé"), "data-explicit"))
    elif "images medicales" in text:
        facts.append(_fact("data", "images médicales", _excerpt(description, "images médicales"), "data-explicit"))
    elif "identite des utilisateurs" in text:
        facts.append(_fact("data", "données d'identité des utilisateurs", _excerpt(description, "identité des utilisateurs"), "data-explicit"))
    elif re.search(r"aucun|aucune|pas de|ne traite pas de", text) and "donnees" in text:
        value = "aucune collecte de données clients" if "collecte de donnees clients" in text else "pas de données médicales" if "donnees medicales" in text else "aucune donnée personnelle"
        facts.append(_fact("data", value, _excerpt(description, "données"), "data-negation"))

    location_terms = [("union europeenne", "Union européenne"), ("france", "France"), ("tunisie", "Tunisie"), ("belgique", "Belgique"), ("lyon", "Lyon"), ("europe", "Europe")]
    for term, value in location_terms:
        if term in text:
            facts.append(_fact("location", value, _excerpt(description, term), "location-explicit"))
            break
    if "entreprises" in text and "en europe" in text:
        facts.append(_fact("market", "entreprises en Europe", _excerpt(description, "entreprises"), "market-explicit"))
    elif "clients en france" in text:
        facts.append(_fact("market", "clients en France", _excerpt(description, "clients"), "market-explicit"))
    elif "etudiants francophones" in text:
        facts.append(_fact("market", "étudiants francophones", _excerpt(description, "étudiants francophones"), "market-explicit"))
    elif "habitants du quartier" in text:
        facts.append(_fact("market", "clients locaux", _excerpt(description, "habitants du quartier"), "market-explicit"))
    elif "clients particuliers" in text:
        facts.append(_fact("market", "artisans et clients particuliers", _excerpt(description, "artisans et clients particuliers"), "market-explicit"))

    unique: dict[tuple[str, str], dict] = {}
    for fact in facts:
        unique.setdefault((fact["domain"], fact["value"]), fact)
    return list(unique.values())
