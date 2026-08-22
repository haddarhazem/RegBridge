from experiments.assessment_stability.ex006_assessment_stability.final_validation import run_final_validation


def test_final_validation_set_is_untouched_and_passes_v1_invariants():
    result = run_final_validation()
    assert result["cases"] == 8
    assert result["equivalent_input_stability"] == 1.0
    assert result["correct_sensitivity"] == 1.0
    assert result["unsupported_claim_rate"] == 0.0
    assert result["source_correctness"] == 1.0
    assert result["category_correctness"] == 1.0
    assert result["snapshot_traceability"] == 1.0
