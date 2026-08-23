# EX-018 — Investment opportunity lifecycle

EX-018 answers RQ-018 by comparing V0 (a mutable opportunity row plus history)
with V1 (stable opportunity identity, immutable versions, and an explicit
current-version pointer). The frozen core benchmark contains 12 scenarios and
the adversarial benchmark contains 8 mutation scenarios.

The invariants are historical reproducibility, no silent rewrite, ownership,
closed exclusion and terminal closure, period validity, missing-field
preservation, stable identity, deterministic current resolution, concurrency
safety, and the informational-only meaning of ACTIVE. The evaluator is
deterministic and candidate-neutral; it does not use an LLM, embeddings, or
financial data.
