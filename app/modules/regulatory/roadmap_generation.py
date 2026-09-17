"""Deterministic startup-launch roadmap generation.

The launch roadmap is a preparation checklist, not a projection of a
regulatory assessment. Persisted, verified assessment conclusions can enrich
the checklist, but they are never required to build it.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping


BASELINE = "BASELINE"
PROJECT_CONTEXT = "PROJECT_CONTEXT"
REGULATORY_ASSESSMENT = "REGULATORY_ASSESSMENT"


def _item(category: str, title: str, justification: str, origin: str, ref: str) -> dict:
    return {
        "item_type": category,
        "title": title,
        "justification": justification,
        "source_conclusion_refs": [f"{origin}:{ref}"],
        "dependency_item_refs": [],
    }


def _normalized(value: str) -> str:
    ascii_value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", ascii_value))


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    normalized = f" {_normalized(text)} "
    return any(term in normalized for term in terms)


def _matching_duplicate(candidate: str, existing: list[dict]) -> dict | None:
    normalized = _normalized(candidate)
    candidate_tokens = set(normalized.split())
    for item in existing:
        current = _normalized(item["title"])
        if current == normalized:
            return item
        current_tokens = set(current.split())
        union = candidate_tokens | current_tokens
        if union and len(candidate_tokens & current_tokens) / len(union) >= 0.72:
            return item
    return None


def has_sufficient_confirmed_context(confirmed: Mapping[str, str | None]) -> bool:
    """Require a small real onboarding foundation before personalization."""
    return sum(bool(str(value or "").strip()) for value in confirmed.values()) >= 2


def generate_launch_items(
    confirmed: Mapping[str, str | None],
    lifecycle: str,
    assessment_result: Mapping | None = None,
) -> list[dict]:
    """Build the baseline, personalize it, then add verified enrichment.

    ``confirmed`` contains only confirmed/corrected values. Assessment
    uncertainties are deliberately excluded: missing evidence is represented
    by a general review item, never promoted to an obligation.
    """
    values = {key: str(value).strip() for key, value in confirmed.items() if str(value or "").strip()}
    creation = lifecycle in {"idea", "startup_in_creation"}
    phase = "avant le lancement" if creation else "pour la prochaine phase d’activité"

    items = [
        _item("legal", "Confirmer la structure juridique adaptée au projet", f"Préparer un cadre juridique cohérent {phase}, sans présumer de la forme à retenir.", BASELINE, "legal-structure"),
        _item("administrative", "Préparer les démarches administratives de création et d’immatriculation", "Identifier et planifier les formalités générales nécessaires à la mise en activité en France.", BASELINE, "administrative-setup"),
        _item("finance", "Mettre en place l’organisation comptable et fiscale", "Préparer la tenue comptable et faire vérifier le régime fiscal adapté par un professionnel compétent.", BASELINE, "accounting-tax"),
        _item("finance", "Préparer le compte bancaire et les moyens de paiement professionnels", "Séparer les opérations du projet et préparer les flux nécessaires à son exploitation.", BASELINE, "banking-payments"),
        _item("legal", "Vérifier les assurances nécessaires à l’activité", "Examiner les risques de l’activité et les couvertures éventuellement nécessaires avant sa mise en marché.", BASELINE, "insurance-review"),
        _item("contracts", "Préparer les contrats et conditions commerciales", "Définir le cadre des relations avec les clients, partenaires et prestataires avant les premiers engagements.", BASELINE, "commercial-contracts"),
        _item("ip", "Examiner la protection des marques, créations et actifs immatériels", "Identifier les actifs à protéger et vérifier les droits nécessaires à leur utilisation.", BASELINE, "ip-review"),
        _item("regulatory", "Vérifier les autorisations et exigences sectorielles applicables", "Conserver un contrôle réglementaire général tant que la couverture spécifique du secteur n’est pas complète.", BASELINE, "sector-review"),
        _item("launch", "Finaliser les prérequis opérationnels avant la mise sur le marché", f"Vérifier que les décisions, responsabilités et moyens essentiels sont prêts {phase}.", BASELINE, "launch-readiness"),
    ]

    data = values.get("data") or values.get("data_context") or ""
    technology = values.get("technology") or ""
    market = values.get("market") or values.get("target_market") or ""
    activity = values.get("activity") or ""
    combined = " ".join(values.values())

    if _contains(data, (" personnel", " client", " utilisateur", " email", " coordonne", " identif", " profil")):
        items.append(_item("privacy", "Préparer la protection des données personnelles", "Les informations confirmées indiquent un traitement de données personnelles ; documenter les traitements et vérifier les exigences applicables avant le lancement.", PROJECT_CONTEXT, "data"))
    if _contains(" ".join((technology, data, activity)), (" saas", " cloud", " heberg", " iot", " connecte", " plateforme", " application web")):
        items.append(_item("security", "Vérifier la sécurité, l’hébergement et la continuité du service", "Le contexte numérique confirmé justifie une revue des mesures techniques et opérationnelles avant la mise en service.", PROJECT_CONTEXT, "technology"))
    if _contains(" ".join((technology, activity)), (" intelligence artificielle", " machine learning", " apprentissage automatique", " algorithme", " ia ", " ia/")):
        items.append(_item("regulatory", "Vérifier l’applicabilité des règles liées à l’intelligence artificielle", "L’usage confirmé d’IA ou de machine learning nécessite une revue d’applicabilité ; aucune obligation détaillée n’est présumée.", PROJECT_CONTEXT, "technology-ai"))
    if _contains(" ".join((technology, activity, values.get("sector", ""))), (" iot", " objet connecte", " capteur", " energie", " energy")):
        items.append(_item("security", "Examiner les exigences techniques et sectorielles des équipements connectés", "Le contexte IoT ou énergétique confirmé justifie une revue de sécurité et d’exigences sectorielles adaptée au produit.", PROJECT_CONTEXT, "technology-iot"))
    if _contains(combined, (" recrut", " salarie", " employe", " embauche", " personnel prevu")):
        items.append(_item("hr", "Préparer les obligations liées aux premiers recrutements", "Le projet confirme un besoin de recrutement ; préparer le cadre employeur avant l’arrivée des salariés.", PROJECT_CONTEXT, "employment"))
    if _contains(combined, (" b2b", " entreprise", " professionnel", " pme")):
        items.append(_item("contracts", "Adapter le parcours contractuel aux clients professionnels", "Le marché B2B confirmé nécessite un parcours clair de proposition, contractualisation et suivi client.", PROJECT_CONTEXT, "market-b2b"))

    result = assessment_result or {}
    for field in ("obligations", "recommendations"):
        for index, conclusion in enumerate(result.get(field, []) or [], 1):
            statement = str(conclusion.get("statement") or "").strip()
            if not statement:
                continue
            conclusion_id = str(conclusion.get("conclusion_id") or f"{field}-{index}")
            duplicate = _matching_duplicate(statement, items)
            if duplicate is not None:
                duplicate["source_conclusion_refs"].append(f"{REGULATORY_ASSESSMENT}:{conclusion_id}")
                continue
            items.append(_item(_assessment_category(statement), statement, "Ajouté à partir d’une conclusion structurée d’une évaluation réglementaire vérifiée.", REGULATORY_ASSESSMENT, conclusion_id))

    for order, item in enumerate(items, 1):
        item["priority_order"] = order
    return items


def _assessment_category(statement: str) -> str:
    value = _normalized(statement)
    rules = (
        ("privacy", ("donnee personnelle", "rgpd", "vie privee")),
        ("security", ("securite", "cyber", "hebergement")),
        ("contracts", ("contrat", "condition generale")),
        ("finance", ("fiscal", "comptable", "paiement")),
        ("ip", ("propriete intellectuelle", "marque", "brevet")),
        ("hr", ("salarie", "employeur", "travail")),
        ("administrative", ("immatriculation", "declaration", "administratif")),
    )
    return next((category for category, terms in rules if any(term in value for term in terms)), "regulatory")


def generate_typed_items(result: dict) -> list[dict]:
    """Backward-compatible helper; production uses ``generate_launch_items``."""
    return generate_launch_items({}, "startup_in_creation", result)
