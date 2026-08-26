# EX-025 audit results

Binary relevance is `STRONG + PARTIAL`; nDCG remains graded. Every non-zero
query has one strong and one partial item, while N21–N24 have zero relevant
items. The old fixed-denominator P@5 gate has an oracle ceiling of `.300` on
the 16-query holdout and is mathematically inappropriate. Zero-match queries
are reported separately: both candidates correctly abstained on 4/4; recall
and R-Precision are undefined for those queries and excluded from aggregates,
while nDCG is conventionally 1.0 for an empty ideal list.

R-Precision and MAP are now frozen for R1. Complete distributions, oracle
ceilings and bootstrap output are in
`artifacts/experiments/ex025_metric_audit.json`. The original EX-025
benchmark, hash, outputs and metrics were preserved.

BGE-M3 code exists in
`experiments/retrieval/ex002_regulatory_retrieval/embedder.py`, but
`BAAI/bge-m3` is not available in the local cache. No production dependency
or model was added. EX-025-R1 remains pending until a fresh holdout and dense
encoder execution are available.
