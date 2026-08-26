# EX-026 results — Sparse recovery

Benchmark: `artifacts/experiments/ex026_recovery_benchmark.json`.

The frozen recovery run evaluated S0–S3 on a fresh holdout. S3 combined the
RD-020 V1 sparse ranking with a deterministic high-signal evidence gate and a
DEV-only score-abstention policy.

| Candidate | Recall@5 | R-Precision | MAP | MRR | nDCG@5 | Abstention |
|---|---:|---:|---:|---:|---:|---:|
| S0 | 0.900 | 0.900 | 0.900 | 1.000 | 0.965 | 0.000 |
| S1 | 0.950 | 0.900 | 0.925 | 1.000 | 0.977 | 0.000 |
| S2 | 0.900 | 0.900 | 0.900 | 1.000 | 0.965 | 1.000 |
| S3 | 0.900 | 0.900 | 0.900 | 1.000 | 0.965 | 1.000 |

S3 passes all frozen utility gates and the false-abstention requirement. It
produced two correct zero-match abstentions, no false matches, and no safety
violations. The DEV threshold was selected before HOLDOUT evaluation.

The result is research evidence for the deterministic sparse-plus-gate-plus-
abstention design. Production implementation is versioned and uses only
APPROVED + MATCHABLE discovery projections; it never loads private full text,
draft fields, embeddings, Qdrant or Mistral.
