"""Deterministic V2 contract semantic/evidence acceptance coverage."""

from __future__ import annotations

import uuid
import json

import pytest

from app.modules.documents.contract_analysis import EvidenceClaim, segment_contract_text, verify_evidence_claim
from app.modules.documents.contract_risk import calculate_contract_risk_index
from app.modules.documents.contract_semantic import (
    ConsistencyDraft,
    EffectiveDateDraft,
    SemanticClauseDraft,
    SemanticContractResult,
    SemanticEvidenceClaim,
    build_verified_semantic_output,
    ProviderContractSemanticAnalyzer,
)
from app.modules.ai.llm import LLMGenerationResponse


SYNTHETIC_CONTRACT_V2 = """PARTIES
Entre EnerSight SAS, ci-apres le Prestataire, et GreenFactory SAS, ci-apres le Client.

ARTICLE 1 - OBJET
Le Prestataire fournit une plateforme SaaS de suivi energetique.

ARTICLE 5 - PAIEMENT
Les factures doivent etre reglees dans un delai raisonnable apres emission.

ARTICLE 6 - DUREE
Le contrat est conclu pour une duree initiale de 12 mois.

ARTICLE 7 - FIN AUTOMATIQUE
Le contrat prend automatiquement fin 24 mois apres sa signature.

ARTICLE 8 - CONFIDENTIALITE
Le Client garde confidentielles les informations du Prestataire.

ARTICLE 9 - PROPRIETE INTELLECTUELLE
Les developpements pourront appartenir au Prestataire ou au Client selon leur nature. La titularite sera definie ulterieurement.

ARTICLE 10 - RESPONSABILITE
La responsabilite financiere du Prestataire n'est soumise a aucune limitation de montant. Aucun plafond contractuel de responsabilite n'est prevu.

ARTICLE 11 - DONNEES PERSONNELLES ET SECURITE
Les parties traitent des donnees personnelles. Le present contrat ne prevoit pas de delai specifique de notification au Client en cas d'incident de securite.

ARTICLE 12 - DROIT APPLICABLE
Le present contrat est soumis au droit francais.
"""


def _section_id(sections, heading_part: str) -> str:
    return next(section.section_id for section in sections if heading_part in (section.heading or ""))


def semantic_fixture() -> SemanticContractResult:
    sections = segment_contract_text(SYNTHETIC_CONTRACT_V2)
    parties = _section_id(sections, "PARTIES")
    payment = _section_id(sections, "PAIEMENT")
    duration = _section_id(sections, "DUREE")
    end = _section_id(sections, "FIN AUTOMATIQUE")
    confidentiality = _section_id(sections, "CONFIDENTIALITE")
    intellectual_property = _section_id(sections, "PROPRIETE")
    liability = _section_id(sections, "RESPONSABILITE")
    data = _section_id(sections, "DONNEES")
    law = _section_id(sections, "DROIT")
    return SemanticContractResult(
        contract_type="Contrat de prestation de services",
        effective_dates=[
            EffectiveDateDraft(
                label="Duree initiale",
                value="12 mois",
                evidence=SemanticEvidenceClaim(section_id=duration, quote="duree initiale de 12 mois"),
            )
        ],
        clauses=[
            SemanticClauseDraft(section_id=parties, clause_type="parties", summary="Les deux parties sont identifiees.", evidence_claims=[SemanticEvidenceClaim(section_id=parties, quote="EnerSight SAS, ci-apres le Prestataire, et GreenFactory SAS, ci-apres le Client")]),
            SemanticClauseDraft(section_id=payment, clause_type="payment", status="AMBIGUOUS", risk_level="medium", summary="Le paiement ne fixe pas de date certaine.", issues=["Le delai raisonnable ne fixe pas une echeance."], why_it_matters="La date d'exigibilite est incertaine.", recommendations=["Preciser un nombre de jours et son point de depart."], evidence_claims=[SemanticEvidenceClaim(section_id=payment, quote="Les factures doivent etre reglees dans un delai raisonnable apres emission")]),
            SemanticClauseDraft(section_id=duration, clause_type="term", summary="Une duree initiale est mentionnee.", risk_level="low", evidence_claims=[SemanticEvidenceClaim(section_id=duration, quote="duree initiale de 12 mois")]),
            SemanticClauseDraft(section_id=end, clause_type="term", summary="Une fin automatique est mentionnee.", risk_level="low", evidence_claims=[SemanticEvidenceClaim(section_id=end, quote="fin 24 mois apres sa signature")]),
            SemanticClauseDraft(section_id=confidentiality, clause_type="confidentiality", status="AMBIGUOUS", risk_level="medium", summary="La confidentialite ne vise explicitement que le Client.", issues=["Obligation reciproque non identifiee."], evidence_claims=[SemanticEvidenceClaim(section_id=confidentiality, quote="Le Client garde confidentielles les informations du Prestataire")]),
            SemanticClauseDraft(section_id=intellectual_property, clause_type="intellectual_property", status="AMBIGUOUS", risk_level="high", summary="La titularite des developpements est differee et incertaine.", issues=["Le titulaire et les droits d'usage ne sont pas clairement attribues."], evidence_claims=[SemanticEvidenceClaim(section_id=intellectual_property, quote="pourront appartenir au Prestataire ou au Client selon leur nature. La titularite sera definie ulterieurement")]),
            SemanticClauseDraft(section_id=liability, clause_type="liability", status="AMBIGUOUS", risk_level="high", summary="Aucun plafond de responsabilite n'est prevu.", issues=["Responsabilite financiere sans plafond."], why_it_matters="L'exposition financiere peut etre importante.", recommendations=["Faire examiner et definir un plafond adapte."], evidence_claims=[SemanticEvidenceClaim(section_id=liability, quote="n'est soumise a aucune limitation de montant. Aucun plafond contractuel de responsabilite n'est prevu")]),
            SemanticClauseDraft(section_id=data, clause_type="data_protection", status="AMBIGUOUS", risk_level="medium", summary="Le traitement des donnees et la notification d'incident doivent etre precises.", issues=["Delai de notification d'incident non defini."], evidence_claims=[SemanticEvidenceClaim(section_id=data, quote="ne prevoit pas de delai specifique de notification au Client en cas d'incident de securite")]),
            SemanticClauseDraft(section_id=data, clause_type="security", status="AMBIGUOUS", risk_level="medium", summary="Le traitement des incidents de securite est incomplet.", issues=["Delai de notification d'incident non defini."], evidence_claims=[SemanticEvidenceClaim(section_id=data, quote="incident de securite")]),
            SemanticClauseDraft(section_id=law, clause_type="governing_law", summary="Le droit applicable est identifie.", risk_level="low", evidence_claims=[SemanticEvidenceClaim(section_id=law, quote="soumis au droit francais")]),
        ],
        consistency_findings=[
            ConsistencyDraft(
                clause_type="term", severity="high", description="La duree initiale de 12 mois et la fin automatique a 24 mois semblent incompatibles.",
                section_ids=[duration, end],
                evidence_a=SemanticEvidenceClaim(section_id=duration, quote="duree initiale de 12 mois"),
                evidence_b=SemanticEvidenceClaim(section_id=end, quote="fin 24 mois apres sa signature"),
                recommendation="Clarifier la duree contractuelle applicable.",
            )
        ],
    )


def _output():
    return build_verified_semantic_output(
        text=SYNTHETIC_CONTRACT_V2,
        document_version_id=uuid.uuid4(),
        source_method="NATIVE",
        result=semantic_fixture(),
    )


def test_document_first_sections_and_semantic_fixture_cover_the_required_cases():
    output = _output()
    by_type = {item.clause_type: item for item in output.clauses if item.status != "CONTRADICTORY"}
    assert output.parties == ["EnerSight SAS - Prestataire", "GreenFactory SAS - Client"]
    assert [(item.name, item.role, item.source_section_id) for item in output.party_details] == [
        ("EnerSight SAS", "Prestataire", "section-1"),
        ("GreenFactory SAS", "Client", "section-1"),
    ]
    assert output.effective_dates == ["Duree initiale: 12 mois"]
    assert by_type["payment"].status == "AMBIGUOUS"
    assert by_type["payment"].risk_level == "medium"
    assert "ARTICLE 5" in by_type["payment"].source_text
    assert by_type["liability"].risk_level == "high"
    assert by_type["intellectual_property"].status == "AMBIGUOUS"
    assert by_type["confidentiality"].status == "AMBIGUOUS"
    assert by_type["data_protection"].status == "AMBIGUOUS"
    assert by_type["security"].clause_type == "security"
    assert "notices" not in by_type
    termination = next(item for item in output.clauses if item.clause_type == "termination")
    assert termination.status == "MISSING" and termination.verification_status == "VERIFIED"
    contradiction = next(item for item in output.clauses if item.status == "CONTRADICTORY")
    assert len(contradiction.evidence) == 2
    assert {"12 mois", "24 mois"} <= {"12 mois" if "12 mois" in item.quote else "24 mois" for item in contradiction.evidence}


def test_evidence_verification_rejects_other_section_and_accepts_safe_normalization():
    sections = segment_contract_text(SYNTHETIC_CONTRACT_V2)
    payment = next(item for item in sections if "PAIEMENT" in (item.heading or ""))
    liability = next(item for item in sections if "RESPONSABILITE" in (item.heading or ""))
    version = uuid.uuid4()
    assert verify_evidence_claim(section=payment, claim=EvidenceClaim(section_id=payment.section_id, quote="Aucun plafond contractuel de responsabilite n'est prevu"), document_version_id=version) is None
    normalized = verify_evidence_claim(section=payment, claim=EvidenceClaim(section_id=payment.section_id, quote="Les factures doivent etre reglees dans un delai raisonnable apres emission"), document_version_id=version)
    assert normalized is not None and "raisonnable" in normalized.quote
    assert verify_evidence_claim(section=liability, claim=EvidenceClaim(section_id=payment.section_id, quote="Aucun plafond contractuel de responsabilite n'est prevu"), document_version_id=version) is None


def test_risk_index_uses_only_verified_material_findings():
    output = _output()
    index = calculate_contract_risk_index(output.clauses)
    assert index.score > 0
    assert any("RESPONSABILITE" in item for item in index.contributors)
    normal = next(item for item in output.clauses if item.clause_type == "governing_law")
    assert normal.risk_level == "low" and normal.status == "FOUND"
    assert all("Droit applicable" not in item for item in index.contributors)
    unverified = normal.model_copy(update={"status": "AMBIGUOUS", "risk_level": "high", "issues": ["unverified"], "verification_status": "UNVERIFIED"})
    assert calculate_contract_risk_index([unverified]).score == 0


@pytest.mark.asyncio
async def test_provider_semantic_analyzer_requires_structured_per_section_and_consistency_outputs():
    sections = segment_contract_text(SYNTHETIC_CONTRACT_V2)[:2]

    class Provider:
        def __init__(self):
            self.calls = []

        async def generate(self, request):
            self.calls.append(request)
            if request.operation == "contract_consistency_analysis":
                body = {"contract_type": "Contrat de prestation de services", "effective_dates": [], "consistency_findings": []}
            else:
                raw = request.messages[-1].content
                section_id = json.loads(raw)["section_id"]
                body = {"section_id": section_id, "clause_type": "other", "summary": "Section analysee.", "status": "FOUND", "risk_level": "low", "evidence_claims": []}
            return LLMGenerationResponse(content=json.dumps(body), model="test-model")

    provider = Provider()
    result = await ProviderContractSemanticAnalyzer(provider).analyze(sections=sections, parties=[])

    assert len(result.clauses) == len(sections)
    assert len(provider.calls) == len(sections) + 1
    assert all(call.response_format for call in provider.calls)


@pytest.mark.parametrize("left,right,expected", [("12 mois", "24 mois", True), ("12 mois", "12 mois", False)])
def test_consistency_fixture_requires_two_distinct_verified_evidence_items(left, right, expected):
    text = SYNTHETIC_CONTRACT_V2
    result = semantic_fixture()
    if not expected:
        text = text.replace("fin 24 mois apres sa signature", "fin 12 mois apres sa signature")
        result = result.model_copy(update={"consistency_findings": []})
    output = build_verified_semantic_output(text=text, document_version_id=uuid.uuid4(), source_method="NATIVE", result=result)
    contradiction = [item for item in output.clauses if item.status == "CONTRADICTORY"]
    assert bool(contradiction) is expected
    if expected:
        quotes = " ".join(item.quote for item in contradiction[0].evidence)
        assert left in quotes and right in quotes
