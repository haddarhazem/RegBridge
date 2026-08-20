# EX-001 - Lightweight vs LangGraph orchestration

## Related Jira

SCRUM-183

## Research Question

What orchestration approach gives the current RegBridge architecture the best
trade-off between explicit authorization control, testability, SCRUM-182
traceability, partial-failure handling, debuggability, extensibility,
provider independence, implementation complexity, dependency footprint, and
runtime overhead?

## Status

COMPLETED

## Motivation

RegBridge needs an explicit authorization boundary before context reaches an
agent and already has a request-correlated, parent/child SCRUM-182 trace
model. This experiment compares a small Python/Pydantic implementation with
LangGraph's low-level `StateGraph` API against the same controlled workflow.



## Hypothesis

H1: A lightweight Python/Pydantic orchestrator may provide stronger explicit
control and lower complexity for RegBridge's current authorization-sensitive
workflow, while LangGraph may provide cleaner workflow composition and better
extensibility as branching/state complexity increases.

## Alternatives

- A: lightweight Python/Pydantic orchestration.
- B: LangGraph 1.2.11 using `StateGraph`.

## Controlled Variables

Both variants use the same Pydantic contracts, deterministic classifier,
router semantics, fail-closed fixture authorization policy, ContextBuilder,
fake agents, output schemas, trace adapter, scenarios, sequential execution
order, Python process, and no real LLM or network. LangGraph persistence,
checkpoints, memory, interrupts, time travel, deployment tooling, and
LangSmith tracing are deliberately disabled/not used because SCRUM-182 is the
trace boundary under evaluation.

## Independent Variable

The orchestration implementation: direct Python control flow versus
LangGraph `StateGraph`.

## Scenarios

S1 single-agent success; S2 two-agent success; S3 deterministic partial
failure; S4 unauthorized context; S5 request/root/child trace hierarchy.

## Metrics and rubric

Scores use 1 (poor) through 5 (excellent), with fixed weights: authorization
control 5, testability 5, traceability 5, debuggability 4, partial failure
handling 4, extensibility 4, provider independence 3, implementation
complexity 3, dependency footprint 2, runtime overhead 1. Scores are
structured engineering judgment, not objective scientific truth. Objective
measurements include scenario pass/fail, variant LOC/files, direct
dependency count, unauthorized loads, fake-agent invocations, trace
hierarchy, and a warm-up/repeated local microbenchmark.

## Procedure

1. Run the shared scenario suite against both factories.
2. Run the runner in one Python process using the same fixtures and trace
   adapter semantics.
3. Record raw JSON under `artifacts/experiments/EX-001/`.
4. Analyze errors and score the fixed rubric without changing weights.

## Reproduction commands

```powershell
python -m pip install -e ".[test,research]"
python -m pytest experiments/orchestration/ex001_custom_vs_framework/tests -q
python -m experiments.orchestration.ex001_custom_vs_framework.runner
```

## Raw artifact location

`artifacts/experiments/EX-001/`

## Limitations

Fake agents are simpler than production agents; only LangGraph is evaluated;
the small workflow may favor lightweight code; future cyclic, stateful, or
human-in-the-loop workflows may change the result; runtime excludes LLM and
network latency; developer familiarity affects qualitative scores; and a
future LangGraph release may alter the comparison.
