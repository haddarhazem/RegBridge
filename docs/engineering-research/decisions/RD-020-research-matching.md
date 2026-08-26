# RD-020 — Startup research-need matching

Status: `FINAL`.

EX-025 was the diagnostic structured-versus-sparse comparison. Its P@5 gate
was invalid for the benchmark relevance density, and its zero-match metric
aggregation defect was corrected before R1.

EX-025-R1 preserved the frozen benchmark (`76ef635011fedc6eb37df3a8fe4b92226aa24ec464500f9382c13ea1c757099a`) and compared V0 structured, V1 sparse, V2 global BGE-M3 dense, V3 field-aware BGE-M3 dense, V4 RRF and V5 weighted hybrid. The conformance audit corrected V3 and V4 without changing gold labels or the holdout. Embeddings were cached with benchmark hash, model ID/revision, L2 normalization and serialization identity.

Final holdout gates: V0 fails Recall, R-Precision and abstention; V1 passes nDCG, Recall, MRR and MAP but fails R-Precision (`.625`) and abstention (`0.00`); V2 fails Recall, R-Precision and abstention; V3, V4 and V5 fail Recall, R-Precision and/or abstention. The four zero-match cases produced no acceptable frozen abstention policy for any candidate.

`Selected: NONE`. No candidate satisfies every frozen utility and safety gate. V6 and V7 were optional controls and were not required for this NONE decision. Reranking is not justified. Chunk size, chunk overlap, splitter strategy and hybrid retrieval remain DEFERRED. The local BGE-M3 encoder is compatible with this R1 protocol, but historical unrelated corpus parity was not established.

SCRUM-211 production is not activated. No matching models, tables, APIs, indexes or migrations are introduced from this decision.
