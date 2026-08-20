# RD-002 - RegBridge orchestration architecture

## Research Question

RQ-001: Which orchestration approach gives the current RegBridge architecture
the best trade-off between authorization control, testability, traceability,
partial-failure handling, debuggability, extensibility, provider independence,
implementation complexity, dependency footprint, and runtime overhead?

## Related Jira

SCRUM-183

## Experiment

EX-001 - Lightweight vs LangGraph orchestration.

## Evidence Summary

Both prototypes passed the same 11-test shared suite across S1-S5. Both
proved zero forbidden-body loads and zero fake-agent invocations for S4,
preserved partial success and failure provenance in S3, and produced correct
SCRUM-182 request/root/child hierarchy in S5. The lightweight prototype was
47 variant LOC with no direct orchestration dependency; LangGraph was 86
variant LOC with one optional direct dependency. Median fake-workflow overhead
was 0.7793 ms versus 9.80315 ms respectively.

## Decision Recommendation

LIGHTWEIGHT

## Why

The lightweight implementation made the authorization-before-context
boundary, deterministic routing, partial aggregation, and SCRUM-182 trace
mapping easiest to inspect and test. It passed every shared scenario while
scoring 176/180 under the frozen rubric, compared with 150/180 for LangGraph.
LangGraph's extensibility scored higher, but that capability did not provide
enough current RegBridge value to offset its additional state/graph ceremony,
dependency footprint, and measured overhead.

## Alternative Rejected

LangGraph is not universally bad and passed all current scenarios. It is not
selected for CURRENT REGBRIDGE because the experiment's authorization and
trace constraints remain clearer and smaller in direct Python/Pydantic code.

## Trade-offs

The lightweight choice gives up framework-provided graph composition and may
require more deliberate code as branching grows. It keeps provider
independence and does not introduce a second persistence/state system.

## Limitations

This is a controlled fake-agent experiment, not a production workload or
scientific benchmark. Only LangGraph was compared, the workflow is small, and
qualitative scores include engineering judgment. The runner's comparison uses
the shared SCRUM-182-semantic in-memory adapter; the database-backed adapter
exists for integration without a competing trace model.

## Revisit When

Re-evaluate if workflows become cyclic, durable pause/resume becomes a product
requirement, human approval must interrupt/resume execution, dozens of
capabilities make custom routing difficult, persistent workflow state separate
from SCRUM-182 becomes necessary, or framework maintenance burden materially
changes. If LangGraph is later selected, reconsider lightweight code if those
conditions disappear or the framework no longer provides measurable value.

This is a research recommendation pending human architecture review. It does
not state that production RegBridge already uses the winner.
