# RD-003 — Regulatory retrieval configuration

## Jira

SCRUM-184

## Research Question

RQ-002

## Experiment

EX-002

## Decision

Select **dense BGE-M3 query retrieval with top-k=5** as the current
production retrieval baseline, subject to the research limitations below.

This is a research configuration decision only. It does not implement a
production `RegulatoryRetriever`, `RegulatoryAgent`, answer generation,
prompt construction, or public endpoint.

## Evidence

EX-002 evaluated the same 20 human-validated questions against the frozen
`reglementation_chunks` collection:

- Recall@3 / @5 / @10: 0.717 / 0.967 / 1.000
- Precision@3 / @5 / @10: 0.433 / 0.360 / 0.190
- MRR: 0.733 / 0.756 / 0.756
- Evidence coverage@3 / @5 / @10: 0.900 / 1.000 / 1.000
- Combined median latency for k=3 / 5 / 10: 330.22 / 334.99 / 347.43 ms

The five-question configuration reaches full question-level evidence
coverage and near-complete point-level recall without the substantial
top-k noise observed at k=10. k=3 loses too much evidence on the hard and
medium subsets.

## Why

k=5 is the best measured balance for this benchmark:

- k=3 misses approved evidence too often.
- k=5 reaches 1.000 evidence coverage and 0.967 point-level recall.
- k=10 raises recall only from 0.967 to 1.000 while reducing precision to
  0.190.
- k=10 has no MRR improvement over k=5 and slightly higher combined median
  latency.

The dense result also showed a ranking problem: nine of 20 questions had at
least one approved point at ranks 4–10, and navigation/tag/index or
wrong-chunk results appeared in observed top positions.

## Rejected alternatives

Only dense k=3 and dense k=10 were directly evaluated and rejected as the
baseline for the reasons above. No hybrid, chunking, alternative embedding,
or production reranking implementation was evaluated.

## Deferred alternatives

- Chunk size tuning
- Chunk overlap tuning
- Splitter strategy comparison
- Hybrid retrieval
- Reranking as a production dependency

Reranking was justified by the ranking evidence and exactly one model,
`BAAI/bge-reranker-v2-m3`, was attempted on the fixed top-10 pool. It did not
complete within repeated five-minute CPU runs, so no incremental reranking
metrics exist and it was not selected.

## Limitations

The historical ingestion/query encoding implementation was not recovered.
The current local BGE-M3 mean-pooling and normalization encoder is a
documented compatible implementation, not proven exact historical parity.
The decision is based on only 20 manually annotated questions, whose
candidates were initially surfaced by the current retriever. The raw corpus
and ingestion pipeline are unavailable, so chunk-size, overlap, splitter,
and reproducible sparse-index experiments remain unavailable. Qdrant network
latency varies, and the result applies only to the frozen 47,881-point
snapshot.

## Revisit conditions

Revisit RD-003 if:

- a reproducible raw corpus and historical encoding implementation become
  available;
- the corpus is materially refreshed;
- the benchmark expands substantially;
- dense retrieval recall becomes inadequate;
- navigation/index-page ranking becomes operationally problematic;
- source filtering requirements appear;
- alternative embeddings become necessary;
- production latency constraints change; or
- a suitable execution environment makes a controlled reranking comparison
  feasible.

