# EX-025 results — startup research-need matching

Benchmark: `research_matching_ex025_v1`; SHA-256:
`b6d47b0714d475c4507c5e9b330340e7c9f38b5562c4c88d4946876598dcdbaf`.
There are 24 startup needs, 30 research snapshots, 8 development needs and
16 holdout needs. Four needs have zero relevant candidates. CORE fields are
domains, technologies, research_problem and keywords. No private text,
evidence, draft, unapproved snapshot or LLM output was used.

Ranking metrics below use the canonical positive-query population: the 12
holdout queries with at least one relevant snapshot. Binary relevance is
STRONG + PARTIAL; nDCG remains graded. Zero-match queries are excluded from
ranking metrics and reported separately.

| Candidate | P@1 | P@3 | P@5 | P@10 | R@1 | R@3 | R@5 | R@10 | Hit@5 | MRR | nDCG@5 | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V0 structured | .750 | .333 | .300 | .167 | .750 | .750 | .750 | .875 | .750 | 1.000 | .904 | .47 | .55 |
| V1 sparse BM25-style | .750 | .396 | .333 | .167 | .750 | .844 | .833 | .875 | .750 | 1.000 | .934 | 14.96 | 17.39 |

The audit found 2 relevant items (1 STRONG and 1 PARTIAL) for every positive
query, giving an old-holdout oracle of P@1=.750, P@3=.500, P@5=.300,
P@10=.150, Recall@5=1.000, MRR=1.000 and nDCG@5=1.000. The original P@5
gate of .70 was mathematically inappropriate for this density. All 4/4
zero-match queries were correctly abstained on by both candidates.

The earlier Recall values (.813/.875) differed from bootstrap (.750/.833)
because zero-match queries had been included in one aggregation and excluded
from the other. This is classified as a zero-match inclusion mismatch. The
canonical evaluator now makes the machine report, rendered report and
bootstrap point estimate agree. R-Precision and MAP were added for R1.

Bootstrap, seed 211, 1,000 query-level resamples:

- V0: nDCG@5=.928 [.888, .967], Recall@5=.750 [.607, .889], MRR=1.000
  [1.000, 1.000], R-Precision=.667 [.542, .800], MAP=.752 [.642, .854].
- V1: nDCG@5=.951 [.913, .983], Recall@5=.833 [.692, .958], MRR=1.000
  [1.000, 1.000], R-Precision=.750 [.611, .893], MAP=.819 [.704, .925].

V0 and V1 were executed. V2/V3 were unavailable because BGE-M3 was not in
the local model cache. V4/V5 depend on V3. V6 had no approved multilingual
reranker configuration. V7 was not executed. Safety violations were all
zero. EX-025 remains diagnostic; semantic/hybrid comparison is pending.
