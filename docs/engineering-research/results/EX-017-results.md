# EX-017 Results

V0 achieved zero unauthorized field exposure and zero unauthorized influence
in the frozen evaluator. Count and pagination operate on the same authorized
filtered dataset. V1 was rejected because post-filtering can expose metadata
through totals, page membership, ordering, or empty pages.

The selected production path uses PostgreSQL query predicates before filters,
sorting, pagination, and counting. It exposes an explicit field allowlist and
does not accept arbitrary ORM field names. The result projection is built from
approved fields rather than serialized ORM objects.

The benchmark is synthetic and does not introduce a search engine, ranking
model, embeddings, or LLM authorization.
