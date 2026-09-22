"""Bounded, provider-free explanations for common product terminology.

This is deliberately not a second router or an LLM-backed chat path.  It
handles only a recognised definition/clarification speech act and a small,
reviewable glossary.  Questions about obligations still belong to the
regulatory agent and continue through its existing evidence pipeline.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class GeneralExplanation:
    answer: str
    term: str | None


def _normal(value: str) -> str:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )
    # Treat apostrophes, typographic punctuation, and hyphens uniformly.  This
    # makes "qu'est-ce que" and "qu’est-ce que" equivalent without keeping a
    # collection of spelling-specific routing rules.
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", normalized)).strip()


class GeneralExplanationResolver:
    """Recognise definition requests independently from regulatory domains."""

    _DEFINITION_CUES = (
        "qu est ce que", "qu est ce qu", "c est quoi", "que signifie", "que veut dire",
        "ca veut dire quoi", "definition de", "definis", "explique",
    )
    _PROJECT_REFERENCES = (
        "mon projet", "notre projet", "ce projet", "my project", "our project", "this project",
    )
    _GLOSSARY = (
        (
            "B2B",
            ("b2b", "business to business", "business-to-business"),
            "B2B signifie Business-to-Business. Il désigne une entreprise qui vend ses produits ou services à d’autres entreprises plutôt qu’aux particuliers.",
        ),
        (
            "SaaS",
            ("saas", "software as a service"),
            "SaaS signifie Software as a Service. Il désigne un logiciel accessible en ligne, généralement par abonnement, sans installation locale par chaque client.",
        ),
        (
            "EnergyTech",
            ("energytech",),
            "EnergyTech désigne les technologies et services numériques appliqués à l’énergie, par exemple pour mesurer, optimiser ou décarboner les usages énergétiques.",
        ),
        (
            "RGPD",
            ("rgpd", "gdpr"),
            "RGPD signifie Règlement général sur la protection des données. Il encadre le traitement des données personnelles dans l’Union européenne.",
        ),
        (
            "donnée personnelle",
            ("donnee personnelle", "donnees personnelles", "personal data"),
            "Une donnée personnelle est une information qui se rapporte à une personne physique identifiée ou identifiable.",
        ),
        (
            "marché cible",
            ("marche cible", "target market"),
            "Le marché cible est le groupe de clients ou d’organisations auquel un produit ou service est destiné en priorité.",
        ),
    )

    def resolve(self, question: str) -> GeneralExplanation | None:
        normalized = _normal(question)
        if not normalized or any(reference in normalized for reference in self._PROJECT_REFERENCES):
            return None
        definition_request = any(cue in normalized for cue in self._DEFINITION_CUES)
        matched = self._match_term(normalized)
        # A terse follow-up such as "Et SaaS ?" remains understandable without
        # importing conversation history, but only for a known glossary term.
        concise_follow_up = matched is not None and len(re.findall(r"[\w-]+", normalized)) <= 3
        if not definition_request and not concise_follow_up:
            return None
        if matched is None:
            return GeneralExplanation(
                answer="Indiquez le terme que vous souhaitez que je clarifie, afin que je puisse vous donner une définition générale.",
                term=None,
            )
        term, answer = matched
        # A regulatory framework remains in the evidence-backed path when the
        # user asks for substantive information about it.  The explicit French
        # "Que signifie …" form is limited to a lexical acronym expansion and
        # is safe to answer without retrieving legal material.
        if term == "RGPD" and not normalized.startswith(("que signifie", "que veut dire")):
            return None
        return GeneralExplanation(answer=answer, term=term)

    @classmethod
    def _match_term(cls, normalized: str) -> tuple[str, str] | None:
        for term, aliases, answer in cls._GLOSSARY:
            if any(
                re.search(rf"(?<!\w){re.escape(_normal(alias))}(?!\w)", normalized)
                for alias in aliases
            ):
                return term, answer
        return None
