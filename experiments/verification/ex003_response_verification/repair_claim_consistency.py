"""Narrow repair for the four cases identified by the human-review gate."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "benchmarks/response_verification_v1.jsonl"


def claim(claim_id: str, text: str, material: bool, support: str, evidence: list[str]) -> dict:
    return {
        "claim_id": claim_id,
        "text": text,
        "material": material,
        "proposed_support": support,
        "proposed_evidence_ids": evidence,
        "expected_support": None,
        "expected_evidence_ids": [],
    }


def main() -> None:
    rows = [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if row["id"] == "VER-007":
            row["category"] = "fully_supported"
            row["mutation_type"] = "corrected_legal_basis_scope"
            row["claims"] = [claim("C1", "Le consentement n'est pas toujours l'unique base légale applicable à un traitement de données personnelles.", True, "supported", ["E1"])]
        elif row["id"] == "VER-008":
            row["category"] = "fully_supported"
            row["mutation_type"] = "evidence_sufficiency_caution"
            row["claims"] = [
                claim("C1", "La durée de conservation des données personnelles doit être communiquée.", True, "supported", ["E1"]),
                claim("C2", "L'extrait ne permet pas de conclure à une conservation indéfinie.", False, "not_applicable", []),
            ]
        elif row["id"] == "VER-012":
            row["category"] = "fully_supported"
            row["mutation_type"] = "corrected_supported_price_rule"
            row["claims"] = [claim("C1", "L'information sur le prix est obligatoire quel que soit le mode de vente.", True, "supported", ["E1"])]
        elif row["id"] == "VER-021":
            row["answer"] = "Dans le cas décrit, l'utilisation des données personnelles pour la prospection commerciale est interdite; les règles propres au canal doivent être vérifiées, mais l'extrait fourni ne les détaille pas."
            row["claims"] = [
                claim("C1", "L'utilisation des données personnelles pour la prospection commerciale est interdite dans le cas décrit.", True, "supported", ["E1"]),
                claim("C2", "Les règles propres au canal doivent être vérifiées.", True, "partially_supported", []),
            ]
    PATH.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
