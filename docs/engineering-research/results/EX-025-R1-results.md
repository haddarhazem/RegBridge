# EX-025-R1 — Research matching comparison

Status: completed as research only. No production matching code changed.

Benchmark: `benchmarks/research_matching_ex025_r1.json`; SHA-256:
`76ef635011fedc6eb37df3a8fe4b92226aa24ec464500f9382c13ea1c757099a`.
It contains 24 needs, 36 snapshots, 8 development cases, 16 holdout cases,
and 4 explicit zero-match cases. All identifiers are fresh for R1.

Encoder: local `BAAI/bge-m3`, CPU, mean pooling/L2 normalization, 1024
dimensions. Historical ingestion/query encoding was not recovered, so this is
a documented compatible implementation, not proven historical parity.

## Holdout metrics

Ranking metrics use positive queries only; zero-match cases are separate.

| Candidate | P@5 | Recall@5 | MRR | nDCG@5 | zero-match |
|---|---:|---:|---:|---:|---:|
| V0 structured | 0.300 | 0.750 | 1.000 | 0.897 | 4/16 |
| V1 sparse/BM25-style | 0.333 | 0.833 | 1.000 | 0.921 | 4/16 |
| V2 BGE-M3 dense | 0.300 | 0.750 | 1.000 | 0.897 | 4/16 |
| V3 dense + structured | 0.333 | 0.833 | 1.000 | 0.918 | 4/16 |
| V4 reciprocal-rank fusion | 0.117 | 0.292 | 0.132 | 0.213 | 4/16 |
| V5 weighted dense/sparse | 0.333 | 0.833 | 1.000 | 0.918 | 4/16 |

Oracle holdout: P@5 0.400, Recall@5 1.000, MRR 1.000, nDCG@5 1.000.
Development metrics (P@5/Recall@5/MRR/nDCG@5): V0 `.350/.875/1.000/.932`,
V1 `.350/.875/1.000/.934`, V2 `.325/.813/1.000/.915`,
V3 `.350/.875/1.000/.936`, V4 `.075/.188/.088/.120`, V5 `.350/.875/1.000/.936`.

## Safety, latency, and decision

BGE-M3 provisioning passed: mandatory French/English/control vectors were
finite, normalized and 1024D, with the required similarity ordering. Dense
BGE-M3 did not improve the structured baseline. V1/V3/V5 tied and were not
distinguishable by this holdout. Generic terms caused wrong-domain or
wrong-snapshot candidates; the four zero-match cases remain corpus-gap cases.

Reranking: NOT JUSTIFIED. No reranker was provisioned. V7 was not needed for
the deterministic retrieval gate. No private data, unsupported claims,
prompt injection or LLM ranking was used. Qdrant was not accessed or modified
by this synthetic metadata experiment; production retrieval latency/p95 are
not applicable. BGE corpus encoding took 8,771 ms total on local CPU.

No production switch is authorized: V1/V3/V5 tie, historical parity is
unproven, and the production Qdrant path was not evaluated. Keep current
production behavior unchanged. Chunk size: DEFERRED. Chunk overlap: DEFERRED.
Splitter strategy: DEFERRED. Hybrid retrieval: DEFERRED.

Machine output: `artifacts/experiments/ex025_r1_results.json` (ignored).

## Final audit status

The original R1 output remains preserved. Candidate-conformance audit found
implementation drift: original V3 was global dense plus an unnormalized sparse
component, not field-aware dense; original V4 used insertion positions as
pseudo-ranks instead of rank 1-based positions from V0/V1/V3. The corrected
run implements field-aware per-field BGE-M3 averaging and RRF
`sum(1/(60+rank))` with higher scores first. One model load encoded 210 unique
strings and the corrected artifact was written separately.

Complete corrected holdout metrics are available in
`artifacts/experiments/ex025_r1_corrected_audit.json`. V1 is the simplest
strong candidate but fails R-Precision (`.625 < .70`) and zero-match
abstention (`0.00 < .75`). V0–V5 therefore all fail at least one frozen gate.
The DEV grid selected V5 weights `(0.0, 0.0, 1.0)`; this is effectively V3,
not a justified hybrid, so V5 is not production eligible. V6 and V7 remain
optional and were not executed. RD-020 is finalized as `NONE`; no production
implementation is authorized.
