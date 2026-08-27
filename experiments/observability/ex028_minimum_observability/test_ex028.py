import json

from run_ex028 import MANIFEST, run


def test_ex028_frozen_failure_comparison_meets_hard_gates():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest["scenarios"]) == 9
    result = run()
    for candidate in ("O0", "O1"):
        metrics = result["candidates"][candidate]
        assert metrics["detection_rate"] == 1.0
        assert metrics["localization_rate"] == 1.0
        assert metrics["correlation_coverage"] == 1.0
        assert metrics["private_content_leakage"] == 0
        assert metrics["secret_leakage"] == 0
        assert metrics["non_actionable_alerts"] == 0
    assert result["selection"] == "O0"
    assert result["worker"] == "NOT_APPLICABLE"
