"""Conversational explanations over an authorized structured contract analysis."""

from __future__ import annotations

import re
import unicodedata

from app.modules.ai.agents import Agent
from app.modules.ai.contracts import AgentRequest, AgentResult


def _normal(value: str) -> str:
    value = "".join(char for char in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", value)).strip()


class ContractAgent(Agent):
    """Answer only from the selected analysis and its source excerpts.

    This is intentionally not a legal-advice model and it performs no hidden
    regulatory-agent chaining.  Contract/RGPD compliance questions remain a
    bounded handoff limitation until multi-capability answer composition has a
    verified public response contract.
    """

    name = "contract-agent"
    capabilities = ("contract",)

    async def run(self, request: AgentRequest) -> AgentResult:
        analysis = request.authorized_context.contract_analysis
        if analysis is None or analysis.status not in {"completed", "partial"}:
            return self._result(
                request,
                "Ouvrez une analyse contractuelle terminée pour poser une question sur un contrat précis.",
                status="failed",
                error_code="contract_analysis_unavailable",
            )
        question = _normal(request.question)
        if analysis.status == "partial" and any(term in question for term in ("entre clauses", "coherence globale", "incoherence entre")):
            return self._result(
                request,
                "Les constats de sections verifies sont disponibles, mais la verification de coherence globale entre les clauses n'est pas terminee. Je ne peux pas en deduire une incoherence inter-clauses.",
            )
        if self._asks_legality(question):
            return self._legality_boundary(request)
        if "rgpd" in question or "conforme" in question or "respecte" in question:
            return self._result(
                request,
                "Je peux expliquer les passages du contrat relatifs aux données personnelles, mais je ne peux pas déterminer à lui seul si le contrat respecte le RGPD. Cette appréciation dépend notamment des traitements réels, des rôles des parties et du droit applicable. Faites examiner les points signalés et, si nécessaire, demandez une analyse réglementaire distincte.",
            )
        if any(term in question for term in ("principal risque", "principaux risques", "quels risques", "quelles clauses devrais")):
            return self._main_risks(request)
        if "non concurrence" in question or "non-concurrence" in request.question.casefold():
            return self._clause_answer(request, "non_compete", absent="Je n'ai pas identifié de clause de non-concurrence dans le document analysé.")
        if any(term in question for term in ("penalite", "pénalité", "retard")):
            return self._penalty_answer(request)
        if "resiliation" in question or "résiliation" in request.question.casefold() or "mettre fin" in question:
            return self._clause_answer(request, "termination", absent="Je n'ai pas identifié de clause de résiliation dans le document analysé.")
        if "duree" in question or "durée" in request.question.casefold() or "expiration" in question:
            return self._duration_answer(request)
        if any(term in question for term in ("propriete intellectuelle", "propriété intellectuelle", "droits d auteur")):
            return self._clause_answer(request, "intellectual_property", absent="Je n'ai pas identifié de clause de propriété intellectuelle dans le document analysé.")
        if "responsabilite" in question or "responsabilité" in request.question.casefold():
            return self._clause_answer(request, "liability", absent="Je n'ai pas identifié de clause de responsabilité dans le document analysé.")
        if any(term in question for term in ("donnees personnelles", "données personnelles", "protection des donnees", "protection des données")):
            return self._clause_answer(request, "data_protection", absent="Je n'ai pas identifié de clause spécifique aux données personnelles dans le document analysé.")
        if "confidential" in question:
            return self._clause_answer(request, "confidentiality", absent="Je n'ai pas identifié de clause de confidentialité dans le document analysé.")
        return self._result(
            request,
            (analysis.summary or "L'analyse structurée est disponible.")
            + " Je peux détailler les risques, la résiliation, la propriété intellectuelle, la responsabilité, les données personnelles ou la confidentialité.",
        )

    @staticmethod
    def _asks_legality(question: str) -> bool:
        return any(term in question for term in ("est il legal", "est il légal", "legalite", "légalité", "peut on signer", "puis je signer", "surement signer"))

    def _legality_boundary(self, request: AgentRequest) -> AgentResult:
        analysis = request.authorized_context.contract_analysis
        review = [clause.title for clause in analysis.clauses if clause.risk_level in {"high", "critical"} or clause.status in {"MISSING", "CONTRADICTORY"}]
        focus = f" Les points qui méritent une revue prioritaire sont : {', '.join(review[:5])}." if review else " Aucun verdict de validité n'est produit par cette analyse."
        return self._result(
            request,
            "Je ne peux pas confirmer de manière inconditionnelle que ce contrat est légal ou qu'il peut être signé sans risque. La validité dépend de la juridiction, des circonstances et du droit applicable." + focus + " Cette analyse aide à repérer des passages à examiner avec un professionnel compétent lorsque nécessaire.",
        )

    def _main_risks(self, request: AgentRequest) -> AgentResult:
        clauses = [item for item in request.authorized_context.contract_analysis.clauses if item.verification_status == "VERIFIED" and (item.risk_level in {"high", "critical", "medium"} or item.status in {"MISSING", "CONTRADICTORY", "AMBIGUOUS"})]
        if not clauses:
            return self._result(request, "Je n'ai pas identifié de point de risque prioritaire dans l'analyse structurée. Cela ne constitue pas une confirmation de validité juridique du contrat.")
        details = []
        for clause in clauses[:6]:
            issue = clause.issues[0] if clause.issues else clause.plain_language_summary
            details.append(f"• {clause.title} — {clause.risk_level} : {issue}")
        return self._result(request, "Les principaux points à examiner sont :\n" + "\n".join(details))

    def _penalty_answer(self, request: AgentRequest) -> AgentResult:
        clause = next((item for item in request.authorized_context.contract_analysis.clauses if item.verification_status == "VERIFIED" and ("penalit" in _normal(item.source_text) or "retard" in _normal(item.source_text))), None)
        if clause is None:
            return self._result(request, "Je n'ai pas identifié de pénalité de retard ni de montant associé dans le document analysé. Je ne peux donc pas en inventer un.")
        return self._explain_clause(request, clause)

    def _clause_answer(self, request: AgentRequest, clause_type: str, *, absent: str) -> AgentResult:
        clause = next((item for item in request.authorized_context.contract_analysis.clauses if item.clause_type == clause_type and item.verification_status == "VERIFIED"), None)
        if clause is None or clause.status == "MISSING":
            return self._result(request, absent)
        return self._explain_clause(request, clause)

    def _duration_answer(self, request: AgentRequest) -> AgentResult:
        clauses = request.authorized_context.contract_analysis.clauses
        contradiction = next(
            (
                item for item in clauses
                if item.clause_type == "term" and item.status == "CONTRADICTORY"
                and item.verification_status == "VERIFIED"
            ),
            None,
        )
        if contradiction is not None:
            return self._explain_clause(request, contradiction)
        return self._clause_answer(
            request,
            "term",
            absent="Je n'ai pas identifié de disposition précise sur la durée dans le document analysé.",
        )

    def _explain_clause(self, request: AgentRequest, clause) -> AgentResult:
        parts = [clause.plain_language_summary]
        if clause.issues:
            parts.append("Point identifié : " + clause.issues[0])
        if clause.why_it_matters:
            parts.append("Pourquoi cela compte : " + clause.why_it_matters)
        if clause.recommendation:
            parts.append("Revue recommandée : " + clause.recommendation)
        if clause.suggested_revision:
            parts.append(clause.suggested_revision)
        quotes = clause.evidence_quotes[:2] if clause.evidence_quotes else ([clause.source_text[:1200]] if clause.source_text else [])
        if quotes:
            parts.append("Preuve du contrat : " + " ; ".join("« " + quote + " »" for quote in quotes))
        return self._result(request, "\n\n".join(parts))

    @staticmethod
    def _result(request: AgentRequest, answer: str, *, status: str = "succeeded", error_code: str | None = None) -> AgentResult:
        analysis = request.authorized_context.contract_analysis
        return AgentResult(
            agent_name=ContractAgent.name,
            capability=request.capability,
            status=status,
            answer=answer,
            warnings=["L'analyse assistée ne remplace pas une validation juridique professionnelle."] if status == "succeeded" else [],
            structured_payload={
                "answer_source": "CONTRACT_ANALYSIS",
                "contract_analysis_id": str(analysis.id) if analysis is not None else None,
                "external_regulatory_retrieval_used": False,
            },
            error_code=error_code,
        )
