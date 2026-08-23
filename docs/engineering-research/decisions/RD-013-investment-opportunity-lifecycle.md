# RD-013 — Investment opportunity lifecycle

For RQ-018, select V1: immutable opportunity versions behind a stable
`InvestmentOpportunity` identity with an explicit current-version pointer.
Create and update the version plus pointer atomically. Use an expected current
version for optimistic concurrency. Close through a dedicated action; CLOSED
is terminal for SCRUM-200 and cannot be silently reopened by PATCH.

The active query must use the current version, `ACTIVE` status, and valid
period in SQL before count, sorting, pagination, or response projection.
Optional fields remain absent/null; no thesis inference or financial execution
is introduced. Future exact-version consumers may store the version ID.

Evidence is moderate: the deterministic frozen benchmark and mutation evaluator
strongly cover lifecycle invariants, but the dataset is synthetic and does not
establish real marketplace behavior. Revisit if reopening, approval workflow,
applications, or financial execution becomes a product requirement.
