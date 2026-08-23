# EX-019 — Event registration consistency

EX-019 answers RQ-019 by comparing V0, one mutable participation state per
user/event with an explicit audit transition, against V1, immutable actions
with a current projection. The frozen benchmark contains 12 core scenarios
and 10 adversarial mutation scenarios.

The invariants are duplicate-free active participation, idempotent interest
and registration, safe withdrawal, cancellation blocking, history and audit
preservation, organizer/participant authorization, user/event isolation,
concurrency safety, and absence of social or private-data side effects.
The evaluator is deterministic and contains no LLM, embedding, or
recommendation behavior.
