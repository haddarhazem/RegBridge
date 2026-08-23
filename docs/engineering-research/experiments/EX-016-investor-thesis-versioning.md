# EX-016 — Investor thesis versioning

EX-016 answers RQ-016 by comparing V0 mutable current profile plus separate
history with V1 immutable thesis versions. The candidate-neutral benchmark has
12 scenarios and the adversarial benchmark has 8. The frozen invariants are
missing-data preservation, historical reproducibility, explicit clearing,
partial-update safety, ownership, ticket validity, and exact snapshot identity.

The experiment uses deterministic normalization only: trim strings and remove
exact duplicates while preserving order. It does not infer sectors, stages,
geography, technology, or ticket values.
