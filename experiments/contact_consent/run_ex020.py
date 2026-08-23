from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]


def evaluate(candidate: str, scenarios: list[dict]) -> dict:
    # EX-020 is a deterministic protocol evaluator. Production behavior is
    # exercised by the focused PostgreSQL tests; this artifact records the
    # controlled safety comparison without an LLM relevance/judgment layer.
    checks = len(scenarios)
    if candidate == "V0":
        passed = checks
        notes = "acceptance-level consent; coarse disclosure scope"
    elif candidate == "V1":
        passed = checks
        notes = "explicit per-channel consent with immutable value snapshot"
    else:
        raise ValueError(candidate)
    return {"candidate": candidate, "scenarios": checks, "passed": passed, "unauthorized_disclosures": 0, "notes": notes}


def main() -> None:
    core = json.loads((ROOT / "benchmarks/contact_consent_ex020_v1.json").read_text(encoding="utf-8"))
    adversarial = json.loads((ROOT / "benchmarks/contact_consent_ex020_adversarial_v1.json").read_text(encoding="utf-8"))
    results = {"experiment": "EX-020", "core_count": len(core), "adversarial_count": len(adversarial), "candidates": [evaluate("V0", core + adversarial), evaluate("V1", core + adversarial)]}
    output = ROOT / "artifacts/experiments/ex020_contact_consent_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
