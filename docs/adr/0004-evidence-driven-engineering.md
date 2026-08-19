# ADR-0004: Use evidence-driven engineering for selected uncertain decisions

## Context

RegBridge contains choices with meaningful uncertainty, including orchestration
architecture, retrieval, verification, model selection, matching, and AI
safety. Popularity or intuition alone is not sufficient evidence for these
choices.

## Decision

Use lightweight, reproducible experiments when multiple credible technical
alternatives exist. Do not experiment on every engineering choice.

## Consequences

Positive:

- defensible decisions;
- stronger reproducibility;
- better technical portfolio evidence;
- easier future comparison.

Negative:

- implementation may take longer;
- benchmarks require maintenance;
- experiments can overfit to a small workload.

## Revisit

Revisit if the research workflow becomes too heavy relative to its decision
value.
