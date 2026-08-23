# RD-011 — Immutable investor thesis versions

Select V1 immutable thesis versions for RQ-016. `InvestorProfile` is a stable
one-per-user identity with an explicit current version pointer. Every changed
thesis creates a new immutable `InvestorThesisVersion`; old versions are never
updated. Future matching reports must store the exact version ID they used.

Fields are user-declared and optional: sectors, stages, geographies,
technologies, ticket minimum/maximum, and currency. Missing values remain
missing. `null` clears a field and `[]` explicitly clears a list. Updates use
an expected current version for optimistic concurrency. No LLM enrichment,
taxonomy inference, FX conversion, or public exposure is included.
