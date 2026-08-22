# EX-008 — Project lifecycle architecture

Ticket: SCRUM-191  
Research question: RQ-009

## Candidates

- V0: the same project aggregate evolves from `idea` to `startup_in_creation` to `existing_startup`.
- V1: a new linked startup project is created and selected relations are copied or referenced.

The frozen architecture-validation set contains 12 synthetic scenarios in
`benchmarks/project_lifecycle_ex008_v1.json`. A separate frozen adversarial set
contains 10 scenarios in
`benchmarks/project_lifecycle_ex008_adversarial_v1.json`. Both are JSON-backed,
candidate-neutral and use no Mistral, Qdrant or private data. Invariants were
authored before candidate evaluation: identity continuity, history
preservation, authorization correctness, reference integrity, audit
completeness, transition correctness, idempotency/concurrency and roadmap
semantic separation.

The runner loads both files and writes per-scenario observations and
programmatic aggregates to
`artifacts/experiments/ex008_project_lifecycle_results.json`. The raw artifact
is intentionally ignored by Git because it is a generated experiment output.

V1 relation plan in the prototype: members and facts COPY when the new project requires independent ownership/context; documents, assessments, snapshots, roadmaps and audit REFERENCE/KEEP through explicit links. This makes duplication measurable and exposes synchronization risk.
