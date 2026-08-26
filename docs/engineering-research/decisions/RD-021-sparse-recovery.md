# RD-021 — Sparse matching recovery

Status: `FINAL`

EX-026 tested a bounded recovery of RD-020's strongest simple candidate. S3
(V1 sparse lexical ranking plus field-aware evidence gating and DEV-calibrated
abstention) passed all frozen utility gates on the fresh holdout:

- Recall@5: `.900`
- R-Precision: `.900`
- MAP: `.900`
- MRR: `1.000`
- nDCG@5: `.965`
- zero-match abstention: `1.000`
- positive false-abstention: `0.000`

Safety influence from private, draft, revoked or non-matchable data was zero.
The selected production strategy is `sparse_research_matching_s3`, using the
exact deterministic tokenization/serialization and a field evidence gate.
S3 does not use Qdrant, BGE-M3, a reranker or Mistral.

RD-020 remains unchanged and records the earlier NONE decision. EX-026 is a
separate bounded recovery decision addressing precision and abstention.
