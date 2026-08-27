# RQ-028 — Minimum production observability

## Question

Which minimum observability strategy detects and localizes critical RegBridge
failures quickly while preserving privacy and avoiding unnecessary overhead?

## Candidates

- O0: structured logs, bounded metrics, and existing request/run correlation.
- O1: O0 plus explicit end-to-end span context.

The frozen comparison uses synthetic failure scenarios F1–F9 in
`benchmarks/manifests/ex028_observability_failures.json`. Worker failure is
not applicable because the current release has no production worker/queue.
