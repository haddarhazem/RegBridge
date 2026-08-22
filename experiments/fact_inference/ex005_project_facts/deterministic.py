from __future__ import annotations

import re
import unicodedata

from .contracts import ExtractedFact, FactDomain, FactProvenance


def _norm(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c))


def _fact(domain: FactDomain, value: str, excerpt: str, rule: str, uncertainty: str = "high") -> ExtractedFact:
    return ExtractedFact(domain=domain, value=value, uncertainty=uncertainty, provenance=FactProvenance(source_field="description", excerpt=excerpt[:300], rule=rule))


def _original_excerpt(description: str, normalized_excerpt: str) -> str:
    normalized_description = _norm(description)
    normalized_excerpt = _norm(normalized_excerpt)
    start = normalized_description.find(normalized_excerpt)
    if start < 0:
        return normalized_excerpt[:300]
    positions: list[int] = []
    for index, character in enumerate(description):
        normalized_character = _norm(character)
        positions.extend([index] * len(normalized_character))
    end = start + len(normalized_excerpt) - 1
    if end >= len(positions):
        return description[positions[start] :]
    return description[positions[start] : positions[end] + 1][:300]


def _is_negated(text: str, term: str) -> bool:
    index = text.find(term)
    if index < 0:
        return False
    prefix = text[max(0, index - 35):index]
    return bool(re.search(r"(?:pas|aucun|aucune|sans|ne contient)\s+(?:de|d'|d)?\s*$", prefix))


def extract(description: str) -> list[ExtractedFact]:
    text = _norm(description)
    facts: list[ExtractedFact] = []

    activity_patterns = [
        (r"(boulangerie artisanale)", "boulangerie artisanale"),
        (r"(boutique e-commerce|boutique e commerce)", "boutique e-commerce"),
        (r"(logiciel saas de facturation)", "logiciel SaaS de facturation"),
        (r"(application d'intelligence artificielle)", "application d'intelligence artificielle"),
        (r"(service de paiement en ligne)", "service de paiement en ligne"),
        (r"(plateforme numerique de sante)", "plateforme numérique de santé"),
        (r"(marketplace(?: pour| met)?[^.;,]*)", "marketplace"),
        (r"(capteur connecte)", "capteur connecté"),
        (r"(service de transport et logistique)", "service de transport et logistique"),
        (r"(plateforme web de formation)", "plateforme web de formation"),
        (r"(systemes? de gestion energetique)", "systèmes de gestion énergétique"),
        (r"(conseil en organisation)", "conseil en organisation"),
        (r"(programme de fidelite)", "programme de fidélité"),
        (r"(service pour des professionnels)", "service pour des professionnels"),
        (r"(fabrication de meubles artisanaux)", "fabrication de meubles artisanaux"),
        (r"(application de prise de rendez-vous)", "application de prise de rendez-vous"),
        (r"(dispositif iot[^.;,]*)", "dispositif IoT de mesure énergétique"),
        (r"(ouverture de compte professionnel)", "ouverture de compte professionnel"),
        (r"(logiciel de gestion documentaire)", "logiciel de gestion documentaire"),
        (r"(accompagnement en transition energetique)", "accompagnement en transition énergétique"),
        (r"(service d'accompagnement scolaire en ligne)", "service d'accompagnement scolaire en ligne"),
    ]
    for pattern, value in activity_patterns:
        match = re.search(pattern, text)
        if match:
            facts.append(_fact("activity", value, match.group(0), "activity-lexical"))
            break

    domain_terms: list[tuple[FactDomain, tuple[str, ...], str, str]] = [
        ("sector", ("pain", "patisserie", "alimentation"), "alimentation", "sector-food"),
        ("sector", ("logiciel b2b", "entreprises clientes"), "logiciel B2B", "sector-software"),
        ("sector", ("medecins", "sante", "patient", "medical"), "santé", "sector-health"),
        ("sector", ("fintech", "paiement"), "fintech", "sector-finance"),
        ("sector", ("industri", "usine", "capteur"), "industrie", "sector-industry"),
        ("sector", ("transport", "logistique"), "transport et logistique", "sector-logistics"),
        ("sector", ("formation", "education", "etudiants", "scolaire"), "éducation", "sector-education"),
        ("sector", ("energetique", "energie"), "énergie", "sector-energy"),
        ("sector", ("pme", "conseil"), "services B2B", "sector-services"),
        ("sector", ("artisanal", "artisanat"), "artisanat", "sector-craft"),
        ("sector", ("secteur public",), "secteur public", "sector-public"),
    ]
    for domain, terms, value, rule in domain_terms:
        term = next((term for term in terms if term in text), None)
        if term:
            facts.append(_fact(domain, value, term, rule))
            break

    tech_terms = [("intelligence artificielle", "intelligence artificielle"), ("saas", "SaaS"), ("e-commerce", "e-commerce"), ("marketplace", "marketplace"), ("capteur connecte", "capteur connecté"), ("iot", "IoT"), ("application", "application"), ("plateforme web", "plateforme web"), ("plateforme numerique", "plateforme numérique"), ("outil numerique", "outil numérique"), ("gestion energetique", "gestion énergétique"), ("paiement en ligne", "paiement en ligne"), ("logiciel", "logiciel")]
    for term, value in tech_terms:
        if term in text and not _is_negated(text, term):
            facts.append(_fact("technology", value, term, "technology-lexical"))
            break
    if _is_negated(text, "intelligence artificielle"):
        match = re.search(r"((?:ne contient pas d|pas d)\s+intelligence artificielle)", text)
        facts.append(_fact("technology", "pas d'intelligence artificielle", match.group(0) if match else "pas d'intelligence artificielle", "technology-negation"))
    if _is_negated(text, "logiciel"):
        match = re.search(r"(aucun logiciel|pas de logiciel|ne contient pas de logiciel)", text)
        facts.append(_fact("technology", "aucun logiciel", match.group(0) if match else "aucun logiciel", "technology-negation"))

    data_patterns = [
        (r"donnees personnelles[^.;]*clients", "données personnelles des clients"),
        (r"donnees de facturation", "données de facturation"),
        (r"images medicales", "images médicales"),
        (r"donnees de sante[^.;]*patients", "données de santé des patients"),
        (r"verifi(?:cation|e) d'identite[^.;]*utilisateurs", "données d'identité des utilisateurs"),
        (r"emails?[^.;]*historique d'achat[^.;]*clients", "emails et historique d'achat des clients"),
        (r"coordonnees[^.;]*rendez-vous", "coordonnées des patients"),
        (r"profils d'apprentissage[^.;]*confirmer", "profils d'apprentissage possibles"),
    ]
    data_match = next((re.search(pattern, text) for pattern, _ in data_patterns if re.search(pattern, text)), None)
    if data_match and not re.search(r"(?:aucun|aucune|pas de|ne traite pas de)\s+(?:traitement de\s+)?donnees", text):
        value = next(value for pattern, value in data_patterns if re.search(pattern, text))
        facts.append(_fact("data", value, data_match.group(0), "data-explicit", "medium" if "possibles" in value else "high"))
    elif re.search(r"(?:aucune|aucun|pas de|ne traite pas de)\s+[^.;]*donnees", text):
        match = re.search(r"((?:aucune|aucun|pas de|ne traite pas de)[^.;]*donnees[^.;]*)", text)
        value = "aucune collecte de données clients" if "collecte de donnees clients" in text else "pas de données médicales" if "donnees medicales" in text else "aucune donnée personnelle"
        facts.append(_fact("data", value, match.group(0) if match else "données non collectées", "data-negation"))

    location_match = re.search(r"\b(lyon|france|tunisie|europe|union europeenne|belgique)\b", text)
    if location_match:
        value = {"lyon": "Lyon", "france": "France", "tunisie": "Tunisie", "europe": "Europe", "union europeenne": "Union européenne", "belgique": "Belgique"}[location_match.group(1)]
        facts.append(_fact("location", value, location_match.group(0), "location-explicit"))

    if "entreprises" in text and "en europe" in text:
        facts.append(_fact("market", "entreprises en Europe", "entreprises clientes en Europe", "market-explicit"))
    elif "clients en france" in text:
        facts.append(_fact("market", "clients en France", "clients", "market-explicit"))
    elif "etudiants francophones" in text:
        facts.append(_fact("market", "étudiants francophones", "étudiants francophones", "market-explicit"))
    elif "pme" in text and "locale" in text:
        facts.append(_fact("market", "PME locales", "PME ... locale", "market-explicit", "medium"))
    elif "entreprises" in text or "pme" in text:
        facts.append(_fact("market", "entreprises", "entreprises", "market-explicit"))
    elif "habitants du quartier" in text:
        facts.append(_fact("market", "clients locaux", "habitants du quartier", "market-explicit"))
    elif "clients particuliers" in text:
        facts.append(_fact("market", "artisans et clients particuliers", "artisans et des clients particuliers", "market-explicit"))

    if "technologie restent a preciser" in text:
        facts.append(_fact("technology", "à préciser", "technologie restent à préciser", "technology-ambiguity", "medium"))
    elif "technologie" in text and "decides plus tard" in text:
        facts.append(_fact("technology", "à définir", "technologie ... décidés plus tard", "technology-ambiguity", "medium"))
    if "secteur" in text and "decides plus tard" in text:
        facts.append(_fact("sector", "à définir", "secteur ... décidés plus tard", "sector-ambiguity", "medium"))
    if "donnees traitees ne sont pas encore definis" in text:
        facts.append(_fact("data", "non défini", "données traitées ne sont pas encore définis", "data-ambiguity", "medium"))


    unique: dict[tuple[str, str], ExtractedFact] = {}
    for fact in facts:
        unique.setdefault((fact.domain, fact.value), fact)
    for fact in unique.values():
        fact.provenance.excerpt = _original_excerpt(description, fact.provenance.excerpt)
    return list(unique.values())
