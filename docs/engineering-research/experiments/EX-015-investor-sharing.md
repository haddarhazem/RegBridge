# EX-015 — Investor sharing authorization

EX-015 answers RQ-015 by comparing V0 resource-level grants with V1 frozen
bundle grants. The machine-readable, candidate-neutral core benchmark has 12
scenarios and the adversarial benchmark has 10. Frozen invariants are default
deny, recipient/project/resource/version binding, revocation, audit
preservation, and no transitive access.

V0 grants one exact allowlisted resource and, for versioned resources, one
exact immutable version. V1 is evaluated as a bundle snapshot: later bundle
definition changes do not alter an existing grant. Neither candidate uses an
LLM, embeddings, Qdrant, or production code.
