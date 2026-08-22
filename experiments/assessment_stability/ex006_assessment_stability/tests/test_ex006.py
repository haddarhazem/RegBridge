from experiments.assessment_stability.ex006_assessment_stability.run_ex006 import main


def test_ex006_has_frozen_split_and_v1_stability():
    result = main()
    assert result["development"] == 8
    assert result["holdout"] == 4
    assert result["summary"]["v1_confirmed_snapshot"]["equivalent_input_stability"] == 1.0
    assert result["summary"]["v1_confirmed_snapshot"]["correct_sensitivity"] == 1.0
    assert result["summary"]["v1_confirmed_snapshot"]["unsupported_claim_rate"] == 0.0
