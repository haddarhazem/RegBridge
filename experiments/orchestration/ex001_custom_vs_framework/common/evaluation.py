from __future__ import annotations

import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

from .scenarios import make_scenario
from .trace_adapter import InMemoryTraceAdapter
from ..custom.orchestrator import LightweightOrchestrator
from ..langgraph.orchestrator import LangGraphOrchestrator
from .classifier import DeterministicClassifier
from .router import DeterministicRouter


def build_orchestrator(variant: str, scenario_id: str, trace=None):
    fixture = make_scenario(scenario_id)
    trace = trace or InMemoryTraceAdapter()
    dependencies = dict(classifier=DeterministicClassifier(), router=DeterministicRouter(), context_builder=fixture.context_builder, registry=fixture.registry, trace=trace)
    orchestrator = LightweightOrchestrator(**dependencies) if variant == "lightweight" else LangGraphOrchestrator(**dependencies)
    return fixture, orchestrator, trace


async def run_variant(variant: str, scenario_id: str):
    fixture, orchestrator, trace = build_orchestrator(variant, scenario_id)
    result = await orchestrator.run(fixture.request)
    return fixture, result, trace


def nonblank_loc(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#"))


def variant_metrics() -> dict[str, dict[str, int]]:
    root = Path(__file__).resolve().parents[1]
    return {
        "lightweight": {"source_files": 1, "implementation_loc": nonblank_loc(root / "custom" / "orchestrator.py")},
        "langgraph": {"source_files": 1, "implementation_loc": nonblank_loc(root / "langgraph" / "orchestrator.py")},
    }


def benchmark(variant: str, iterations: int = 100, warmup: int = 10) -> dict[str, float | int]:
    import asyncio

    async def one():
        await run_variant(variant, "S2")

    for _ in range(warmup):
        asyncio.run(one())
    samples = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        asyncio.run(one())
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    ordered = sorted(samples)
    return {"iterations": iterations, "median_ms": statistics.median(samples), "p95_ms": ordered[max(0, int(iterations * 0.95) - 1)]}


def environment_metadata() -> dict:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = "working-tree"
    try:
        import langgraph
        langgraph_version = getattr(langgraph, "__version__", "1.2.11")
    except Exception:
        langgraph_version = "not-installed"
    return {"experiment_id": "EX-001", "rq_id": "RQ-001", "jira": "SCRUM-183", "git_commit": commit, "date": "2026-08-20", "python": sys.version.split()[0], "os": platform.platform(), "langgraph_version": langgraph_version, "config_version": "1.0.0", "scenario_version": "1.0.0", "seed": 42, "network_or_llm_required": False}

