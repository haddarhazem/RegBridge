# ADR-0006: Use lightweight Python/Pydantic orchestration

## Status

Accepted / current for RegBridge V1

## Context

SCRUM-183 required a production orchestration choice after the research gate
for RQ-001. EX-001 compared lightweight Python/Pydantic orchestration with
LangGraph StateGraph. RD-002 records the accepted human-reviewed decision.

## Decision

Use explicit, sequential Python/Pydantic orchestration for current RegBridge
production code. The flow owns intent classification, deterministic routing,
authorized ContextBuilder invocation, validated AgentRequest creation,
1..N agent execution, structured aggregation, and SCRUM-182 root/child trace
integration.

Production agents remain provider-neutral and receive only minimized Pydantic
DTOs. Repositories remain the direct database boundary; authorization occurs
before sensitive project projection loading.

## Alternatives

- LangGraph StateGraph: evaluated in EX-001 and not selected for current V1.
- Lightweight custom orchestration: selected.

## Evidence

EX-001 passed all shared scenarios for both candidates. Lightweight scored
176/180 versus 150/180 under the fixed rubric, with documented median fake
workflow overhead of 0.7793 ms versus 9.80315 ms. These are controlled
engineering measurements, not claims about end-to-end model performance.

## Consequences

Positive:

- explicit control flow and authorization boundaries;
- direct SCRUM-182 trace mapping;
- deterministic testing without a provider;
- low dependency footprint and provider independence.

Negative:

- RegBridge owns routing and state-transition code;
- advanced workflow functionality must be implemented explicitly if needed;
- custom complexity may grow as workflows become more stateful.

## Revisit conditions

Revisit if workflows become cyclic, durable pause/resume is required, human
approval must interrupt/resume workflows, the orchestration graph becomes
substantially more complex, many capabilities make custom control difficult,
or persistent workflow state beyond SCRUM-182 traces becomes necessary.
