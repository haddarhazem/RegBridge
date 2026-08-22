import json

from experiments.contract_verification.run_ex011 import EvidenceResolver, REASON_CODES, VerificationOutput, mutation_detected


def test_exact_quote_resolver_derives_offsets():
    text = "First clause. Payment is due within 10 days. End."
    result = EvidenceResolver.resolve(text, "Payment is due within 10 days.")
    assert result == {"status": "RESOLVED", "start_char": 14, "end_char": 44}
    assert text[result["start_char"]:result["end_char"]] == "Payment is due within 10 days."


def test_resolver_rejects_missing_and_ambiguous_quotes():
    assert EvidenceResolver.resolve("No matching clause.", "Payment is due.")["status"] == "INVALID"
    assert EvidenceResolver.resolve("Same clause. Same clause.", "Same clause.")["status"] == "AMBIGUOUS"


def test_verifier_schema_is_bounded():
    item = VerificationOutput.model_validate({"verdict": "UNSUPPORTED", "reason_code": "NEGATION_ERROR", "corrected_type": None, "evidence_sufficient": False})
    assert item.reason_code in REASON_CODES
    try:
        VerificationOutput.model_validate({"verdict": "SUPPORTED", "reason_code": "free_form", "evidence_sufficient": True})
    except ValueError:
        pass
    else:
        assert "free_form" not in REASON_CODES


def test_evaluator_detects_required_unsafe_mutations():
    for mutation in ("negation_supported", "unrelated_supported", "fabricated_supported", "recommendation_as_fact", "conflict_supported", "prompt_injection_followed", "conditional_overstatement"):
        assert mutation_detected("UNSUPPORTED", mutation)
    for mutation in ("quote_changed", "wrong_document_version"):
        assert mutation_detected("SUPPORTED", mutation)
    assert mutation_detected("UNCERTAIN", "conflict_supported")
