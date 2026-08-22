"""Deterministic, regulation-focused idea-project onboarding decisions."""

from __future__ import annotations

import unicodedata
from typing import Any

from app.modules.projects.schemas import OnboardingField, OnboardingQuestion


QUESTIONS: dict[OnboardingField, str] = {
    "activity": "Quelle activité votre projet prévoit-il ?",
    "sector": "Dans quel secteur cette activité sera-t-elle exercée ?",
    "technology": "Quelle technologie ou quel traitement numérique votre projet utilisera-t-il ?",
    "data": "Quelles données votre projet prévoit-il de collecter ou traiter ?",
    "market": "Quel marché ou quels clients ciblez-vous ?",
    "location": "Où l'activité sera-t-elle exercée ou proposée ?",
}


def confirmed_fields(project: Any) -> list[OnboardingField]:
    values = project.confirmed_fields or {}
    return [field for field in QUESTIONS if values.get(field) == "confirmed"]


def _text(project: Any) -> str:
    text = " ".join(str(value or "") for value in (project.activity, project.sector, project.technology)).lower()
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )


def _technology_relevant(project: Any) -> bool:
    return any(term in _text(project) for term in ("tech", "logiciel", "numerique", "saas", "application", "plateforme", "ia", "web", "ecommerce", "e-commerce", "marketplace", "capteur", "connecte", "iot", "transport", "logistique", "energie"))


def _data_relevant(project: Any) -> bool:
    return any(term in _text(project) for term in ("donnee", "client", "patient", "sante", "paiement", "email", "collect", "trait", "ecommerce", "e-commerce", "marketplace", "saas", "intelligence artificielle", "formation", "connecte", "iot"))


def relevant_fields(project: Any) -> list[OnboardingField]:
    fields: list[OnboardingField] = ["activity", "sector"]
    if _technology_relevant(project):
        fields.append("technology")
    if _data_relevant(project):
        fields.append("data")
    fields.extend(["market", "location"])
    return fields


def next_questions(project: Any) -> list[OnboardingQuestion]:
    confirmed = set(confirmed_fields(project))
    return [OnboardingQuestion(field=field, question=QUESTIONS[field]) for field in relevant_fields(project) if field not in confirmed]


def onboarding_status(project: Any) -> str:
    return "complete" if not next_questions(project) else "in_progress"
