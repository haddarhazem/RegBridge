# RD-001 - Correlated, allowlisted hybrid AI execution traces

## Research Question

What trace model provides enough information for debugging, reproducibility,
and future GenAI experiments while minimizing unnecessary persistence of
sensitive application data?

## Related Jira

SCRUM-182

## Experiments

None. This is an architectural/design evaluation, not a runtime performance
experiment or benchmark.

## Evidence Summary

The evaluated designs were compared against request reconstruction, parent /
child execution, queryability, provider neutrality, data minimization, and
future experiment metadata requirements.

## Decision

1. Use a unique `agent_runs.id`, a shared non-unique `request_id`, and
   `parent_run_id` for hierarchy.
2. Use hybrid storage: stable execution dimensions in SQL columns and
   evolving structured payloads in JSONB.
3. Validate an explicit allowlist-based Pydantic projection before persistence.
4. Do not create persistent conversation threads or messages for anonymous
   visitors; an optional anonymous technical run must remain minimal.

## Why

Shared correlation reconstructs all runs caused by one request without
confusing request identity with run identity. Hybrid storage keeps common
queries constrained and searchable while allowing provider-neutral metadata to
evolve. Pre-persistence allowlisting and redaction reduce accidental secret
and private-content retention. Authenticated-only history avoids creating
anonymous profiles through traces.

## Alternatives Rejected

- Unique `request_id` per run: cannot represent a complete request trace.
- SQL columns only: forces migrations for evolving provider metadata.
- JSONB only: weakens constraints and stable querying.
- Persist everything then redact: exposes sensitive data to the persistence
  boundary and risks irreversible leakage.
- Persistent anonymous threads: creates recoverable history and tracking risk.

## Trade-offs

The explicit contracts require future agents to create a trace projection.
Some raw context is intentionally not reproducible, especially for anonymous
requests. JSONB remains flexible but still needs versioned contracts.

## Limitations

No scale or performance benchmark was required. Retention duration remains an
open production decision. Provider metadata may evolve, and distributed
tracing or multiple independently important model calls may require a future
reassessment.

## Revisit When

Revisit when orchestration becomes deeply nested or cyclic, distributed
services require trace propagation, one run performs many independently
important model/tool calls, retention requirements are finalized, or experiment
volume makes the current metadata insufficient.
