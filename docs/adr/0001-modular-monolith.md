# ADR-0001: Use a modular monolith for RegBridge V1

Status: Accepted

## Context

RegBridge contains several domains, but one developer currently develops the product. Premature microservices would add deployment, network, and operations complexity. AI agents are logical capabilities, not automatically services.

## Decision

Use one backend deployment separated into explicit internal modules.

## Consequences

Positive: simpler development, testing, local setup, transactions, and refactoring, with less operational overhead.

Trade-offs: module boundaries require discipline, independent scaling is initially limited, and later extraction may require refactoring.

## Revisit when

Revisit if independently scaling workloads become necessary, teams own domains independently, deployment isolation becomes necessary, or operational evidence justifies extraction.
