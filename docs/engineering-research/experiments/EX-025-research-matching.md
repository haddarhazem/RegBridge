# EX-025 — Startup research-need matching

Research identity: RQ-025 / EX-025 / RD-020.

The frozen benchmark contains 24 startup research-need snapshots and 30
approved-like research discovery snapshots. It uses only CORE fields:
domains, technologies, research_problem and keywords. Sixteen needs form the
independent holdout; eight are development-only. Four holdout/development
needs have no relevant research candidate and remain in all aggregate metrics.

V0 is deterministic structured overlap. V1 is a deterministic BM25-style
sparse lexical scorer. Dense, field-aware dense, hybrid, reranker and LLM
variants are recorded unavailable because no already-approved research
matching encoder/index or reranker configuration was available without
introducing an unvalidated path. No private paper text, evidence, draft
discovery, or unapproved snapshot is used.

The benchmark hash and candidate configuration are recorded in the generated
EX-025 artifact. The holdout is not used for tuning.
