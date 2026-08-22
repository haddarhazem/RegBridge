# RD-005 — Project lifecycle transition strategy

Status: ACCEPTED  
Ticket: SCRUM-191  
Research: EX-008 / RQ-009

## Decision

Keep one persistent project identity and evolve `projects.project_type` through the explicit states:

`idea -> startup_in_creation -> existing_startup`

Record each successful transition in the existing audit log. Do not create a linked startup project or copy project artifacts.

## Evidence

EX-008 executed both candidates against a frozen JSON-backed original benchmark
of 12 scenarios and a separate adversarial benchmark of 10 scenarios. The
programmatic evaluator found 100% identity, history, authorization, reference,
audit, transition and idempotency/concurrency results for both candidates. V0
required zero duplication and zero synchronization rules; V1 required 7
duplication operations on each benchmark, 12 synchronization rules on the
original set and 14 on the adversarial set. V0 passed all 22 scenarios; V1
passed 13 because its linked-project model violated the frozen no-arbitrary-
duplication invariant. V0 therefore wins the data-integrity priority without
sacrificing auditability or authorization.

The historical 91.7% transition score was an evaluator limitation: invalid T11
was counted as a failure rather than a correctly rejected transition. The
JSON-backed evaluator compares observed validity with expected validity and
scores T11 correctly.

Creation roadmaps and future startup compliance roadmaps remain distinct artifact purposes on the same project aggregate.

## Revisit conditions

Revisit if a future requirement introduces legally separate entities, independent ownership/billing, or an artifact that must have an independent authorization boundary.
