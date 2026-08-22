from experiments.roadmap_generation.ex007_roadmap_generation.run_ex007 import main


def test_ex007_selects_typed_generation_on_frozen_split():
    result = main()
    assert result["development"] == 10
    assert result["holdout"] == 6
    assert result["summary"]["v1_typed"]["unsupported_step_rate"] == 0.0
    assert result["summary"]["v1_typed"]["type_correctness"] == 1.0
    assert result["summary"]["v1_typed"]["traceability_correctness"] == 1.0
