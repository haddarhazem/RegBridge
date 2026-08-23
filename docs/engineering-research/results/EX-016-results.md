# EX-016 Results

V1 immutable thesis versions satisfy the historical and snapshot invariants
with one authoritative current pointer. V0 can represent current values but
requires synchronization between a mutable row and separate history, leaving
more opportunity for a matching snapshot to follow current state accidentally.

V1 is selected for production. Each update creates a new immutable version;
identical normalized updates reuse the current version. Omitted PATCH fields
are preserved, explicit `null` clears a value, and `[]` is stored as an
explicitly empty preference list. The raw programmatic output is
`artifacts/experiments/ex016_investor_thesis_versioning_results.json`.

The benchmark is synthetic. It does not establish investment suitability or
matching quality. Future matching must consume an exact thesis version ID.
