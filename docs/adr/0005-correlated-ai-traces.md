# ADR-0005: Use correlated, allowlisted hybrid AI execution traces

Status: Accepted

## Context

RegBridge needs persistent execution evidence for debugging and future
reproducible engineering without turning traces into a copy of application
context or private documents. SCRUM-182 evaluated correlation, storage, and
privacy boundaries. See [RD-001](../engineering-research/decisions/RD-001-ai-trace-model.md).

## Decision

Use a unique run ID, a shared non-unique request correlation ID, and a
parent/child run hierarchy. Store stable queryable fields in SQL columns and
structured evolving metadata in JSONB. Persist only explicit trace-safe
Pydantic projections after validation, minimization, and redaction.

Persistent conversation history is authenticated-only. Anonymous technical
traces, where required, remain minimal and contain no conversation history.

## Alternatives

Rejected alternatives are documented in RD-001: per-run request IDs, SQL-only
or JSONB-only storage, post-persistence redaction, and persistent anonymous
threads.

## Consequences

The design supports request reconstruction, provider neutrality, and future
experiment/configuration references. Future agents must define trace-safe
projections, and some raw context is intentionally not retained.

## Security implications

Bearer tokens, credentials, authorization headers, arbitrary ORM dumps, full
private documents, and complete system prompts are not trace payloads. Error
messages are sanitized before storage.

## Revisit conditions

Revisit for distributed trace propagation, cyclic/deep orchestration, multiple
independently important model calls per run, finalized retention requirements,
or materially increased experiment volume.
