from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .common.evaluation import benchmark, environment_metadata, run_variant, variant_metrics


SCENARIOS = ["S1", "S2", "S3", "S4", "S5"]


async def collect_scenarios():
    output = {}
    security = {}
    for scenario_id in SCENARIOS:
        output[scenario_id] = {}
        for variant in ("lightweight", "langgraph"):
            fixture, result, trace = await run_variant(variant, scenario_id)
            output[scenario_id][variant] = result.model_dump(mode="json")
            security.setdefault(variant, {})[scenario_id] = {
                "unauthorized_resource_loads": len(fixture.context_builder.repository.loaded_body_ids),
                "fake_agent_invocations": sum(fixture.agents[name].invocations.total() for name in fixture.agents),
                "trace_run_count": len(trace.for_request(fixture.request.request_id)),
                "trace_hierarchy_correct": all(run.request_id == fixture.request.request_id for run in trace.for_request(fixture.request.request_id)),
            }
    return output, security


def main() -> None:
    scenarios, security = asyncio.run(collect_scenarios())
    root = Path("artifacts/experiments/EX-001")
    root.mkdir(parents=True, exist_ok=True)
    raw = {"environment": environment_metadata(), "scenarios": scenarios, "security": security, "variant_metrics": variant_metrics()}
    raw["benchmark"] = {variant: benchmark(variant) for variant in ("lightweight", "langgraph")}
    (root / "runs.json").write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(raw, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

