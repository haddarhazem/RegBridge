# EX-002 — Regulatory retrieval results

## Jira

SCRUM-184

## Research Question

RQ-002: Given the frozen French regulatory corpus in Qdrant, which retrieval
configuration retrieves the most useful expected official evidence while
keeping latency and complexity reasonable?

## Environment

- Branch: current working branch (commit `240d1008d6511a5262c5d0110aab8ba8b63a7901`)
- Python: 3.12.6
- Qdrant client: 1.18.0
- Embedding model: `BAAI/bge-m3`
- Query device: CPU
- Collection: `reglementation_chunks`
- Corpus: 47,881 points, 45,982 indexed vectors, 2 segments
- Vector configuration: 1,024 dimensions, cosine distance
- Qdrant operations executed: metadata/count/query reads only

The historical ingestion and query encoding implementation was not recovered.
The local mean-pooling and L2-normalized BGE-M3 encoder is a documented
compatible implementation, not proven historical parity.

## Benchmark

- Total questions: 25
- Evaluated human-validated questions: 20
- Excluded pending questions: 5
- Pending IDs: REG-004, REG-007, REG-021, REG-022, REG-025
- Duplicate IDs: 0
- JSONL parse errors: 0
- Human-validated questions missing evidence: 0
- Invalid point locators: 0

Only exact human-approved `point_id` matching was used. No pending question
participated in any metric, and no label was changed.

## Dense retrieval configurations

The same benchmark, collection, stored vectors, query encoder, Qdrant
configuration, and evidence matching rules were used for k=3, k=5, and k=10.
Only the requested top-k changed. No score threshold, HNSW setting, exact-search
setting, re-embedding, or corpus mutation was used.

Definitions:

- Recall@k: matched expected point IDs in the first k divided by the expected
  point-ID count.
- Precision@k: matched retrieved point IDs in the first k divided by k.
- Precision interpretation: Precision@k is measured against the finite set of explicitly annotated expected point IDs. Because relevance annotations are not exhaustive over the entire corpus, an unannotated retrieved point is not necessarily semantically or legally irrelevant. Precision values are therefore used primarily for relative comparison between the evaluated configurations.
- MRR: reciprocal rank of the first matched expected point ID, averaged over
  questions.
- Evidence coverage@k: proportion of evaluated questions with at least one
  matched expected point ID in the first k.
- Cost: No per-query model-provider cost was measured because BGE-M3 inference was executed locally on CPU. Infrastructure/electricity costs were not attributed per query.

| k | Recall@k | Precision@k | MRR | Evidence coverage | Qdrant median (ms) | Qdrant p95 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 0.717 | 0.433 | 0.733 | 0.900 | 196.29 | 502.71 |
| 5 | 0.967 | 0.360 | 0.756 | 1.000 | 194.81 | 567.03 |
| 10 | 1.000 | 0.190 | 0.756 | 1.000 | 200.51 | 336.00 |

The point-level recall and coverage figures are aggregate means over the 20
questions. Precision counts only exact approved point IDs as relevant.

## Latency

There were 20 final samples per measurement family after one model/Qdrant
warm-up. These are retrieval-pipeline measurements, not complete future RAG
answer latency.

| Component | Median (ms) | p95 (ms) | Samples |
|---|---:|---:|---:|
| Query embedding | 135.43 | 190.08 | 20 |
| Qdrant, k=3 | 196.29 | 502.71 | 20 |
| Qdrant, k=5 | 194.81 | 567.03 | 20 |
| Qdrant, k=10 | 200.51 | 336.00 | 20 |
| Combined, k=3 | 330.22 | 693.25 | 20 |
| Combined, k=5 | 334.99 | 900.11 | 20 |
| Combined, k=10 | 347.43 | 470.77 | 20 |

## Per-question results

The raw artifact preserves all retrieved points, scores, payload excerpts,
latencies, and exact matches. The following records the observed rank of each
approved evidence point at k=10; `—` would mean it was absent from top-10.

| Question | Approved evidence ranks at k=10 |
|---|---|
| REG-001 | 3, 6, 8 |
| REG-002 | 2, 3 |
| REG-003 | 1 |
| REG-005 | 2, 4 |
| REG-006 | 2, 3 |
| REG-008 | 1, 3 |
| REG-009 | 4, 5 |
| REG-010 | 1 |
| REG-011 | 1, 3 |
| REG-012 | 5 |
| REG-013 | 1 |
| REG-014 | 1, 2 |
| REG-015 | 1, 3 |
| REG-016 | 1, 2 |
| REG-017 | 1 |
| REG-018 | 1, 3, 4 |
| REG-019 | 1, 5 |
| REG-020 | 1, 4 |
| REG-023 | 3, 4, 5 |
| REG-024 | 2, 5 |

No approved evidence point was absent from top-10. Nine of 20 questions had
at least one approved point at rank 4–10.

## Difficulty analysis

Descriptive only; this benchmark is too small for statistical significance.

| Difficulty | Questions | Recall@3 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|
| Easy | 3 | 1.000 | 1.000 | 1.000 |
| Medium | 9 | 0.704 | 1.000 | 1.000 |
| Hard | 8 | 0.625 | 0.917 | 1.000 |

## Topic analysis

Recall by topic is descriptive:

| Topic | Questions | Recall@3 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|
| rgpd | 4 | 0.708 | 0.833 | 1.000 |
| business_creation | 3 | 0.667 | 1.000 | 1.000 |
| employment | 3 | 0.667 | 1.000 | 1.000 |
| ai_digital | 2 | 0.583 | 1.000 | 1.000 |
| ai_rgpd | 1 | 0.500 | 1.000 | 1.000 |
| consumer | 4 | 1.000 | 1.000 | 1.000 |
| consumer_ecommerce | 1 | 1.000 | 1.000 | 1.000 |
| administrative | 1 | 0.333 | 1.000 | 1.000 |
| cross_topic | 2 | 0.500 | 1.000 | 1.000 |
| employment_rgpd | 1 | 1.000 | 1.000 | 1.000 |

## Error analysis

These are actual observed top-10 results, not inferred failures:

- Expected evidence not retrieved: none among the 20 human-validated
  questions at k=10.
- Evidence below the top useful positions: REG-001 had approved points at
  ranks 6 and 8; REG-009 at ranks 4 and 5; REG-018 at rank 4; REG-019 at
  rank 5; REG-020 at rank 4; REG-023 at ranks 4 and 5; and REG-024 at rank 5.
- Correct document but wrong chunk: REG-005 returned a non-approved chunk 6
  from the same CNIL blockchain document at rank 1, while approved chunks
  appeared at ranks 2 and 4. REG-001 similarly returned a CNIL tag-page chunk
  before the approved document chunks.
- Navigation/tag/index noise: REG-001 returned
  `www.cnil.fr/fr/tag/Blockchain` at rank 1; REG-002 returned the CNIL
  French-English data-protection lexicon at rank 1; and REG-016 returned a
  Service-Public `Commerce en ligne` index page among the top results.
- Semantic ambiguity: REG-018 returned an annual-report AI page before all
  three approved AI-regulation points; REG-019 returned a CNIL AI/GDPR
  recommendations page before its second approved point.
- Lexical ambiguity: REG-003 returned a CNIL commercial-prospecting
  transmission page at rank 2 alongside the approved point at rank 1.
- Apparent corpus gaps: none were observed for the manually approved
  evidence, because all approved point IDs were present by k=10. This does
  not establish completeness for unannotated corpus content.

The observations support a ranking-quality problem rather than a top-10
coverage problem.

## Reranking Gate

**JUSTIFIED — test attempted, result inconclusive on the available CPU.**

The gate criteria were met by the dense result: Recall@10 was 1.000, while
Precision@3 was 0.433 and nine questions placed at least one approved point
below rank 3. Actual tag, lexicon, navigation, index, and wrong-chunk
examples were observed.

Exactly one multilingual reranker was attempted:
`BAAI/bge-reranker-v2-m3`, using the fixed dense top-10 candidate pool. The
model was not added to production dependencies and no valid incremental
metrics were produced: CPU inference exceeded five minutes on repeated
bounded attempts, including a 128-token truncation attempt, without completing
the 20-question artifact. Therefore no reranker gain or latency claim is
made. Reranking is not selected for production by this experiment.

## Hybrid Retrieval

**DEFERRED.** The frozen corpus exposes dense vectors but no reproducible
sparse representation, and the original raw corpus is unavailable for
controlled sparse-index reconstruction.

## Chunking / overlap / splitter

- Chunk size: **DEFERRED**
- Chunk overlap: **DEFERRED**
- Splitter strategy: **DEFERRED**

The raw source corpus and historical ingestion implementation were not
recovered. Existing stored chunk boundaries were not changed.

## Metadata / provenance observations

The frozen collection manifest records the observed payload keys:
`source_domain`, `url`, `parent_url`, `chunk_index`, and `content`.
Organization, title, and date are not guaranteed structured payload fields.
The experiment did not infer relevance from URLs or metadata; matching used
only approved point IDs.

## Corpus integrity

| Check | Value |
|---|---:|
| Starting points_count | 47,881 |
| Ending points_count | 47,881 |
| Changed | NO |
| Starting indexed_vectors_count | 45,982 |
| Ending indexed_vectors_count | 45,982 |

The observed collection configuration also remained 1,024-dimensional cosine
vectors with two segments. No mutation operation was executed by the
experiment code.

## Limitations / threats to validity

- Only 20 human-validated questions were evaluated.
- The benchmark was manually constructed.
- The annotations are not exhaustive over all 47,881 points.
- Annotation candidates were originally surfaced by the current retriever,
  creating possible retrieval-induced annotation bias.
- Exact historical ingestion/query embedding parity could not be proven.
- The raw source corpus is unavailable for reproducible rechunking.
- Chunk size, overlap, and splitter strategy could not be evaluated.
- Qdrant Cloud network latency varies.
- Results apply only to this frozen corpus snapshot.
- Pending questions were intentionally excluded.
- The reranker gate identified a ranking issue, but the one-model reranker
  attempt was not operationally measurable on this CPU environment.

## EX-002 result

Dense BGE-M3 retrieval achieves complete approved-evidence coverage by k=5
for this benchmark, with Recall@5 0.967, Evidence coverage@5 1.000, MRR
0.756, and lower retrieval noise than k=10. k=3 is materially weaker on
coverage; k=10 adds little measured ranking value while reducing precision.
The dense top-5 configuration is the supported research baseline.

## Research artifacts

- Protocol: `docs/engineering-research/experiments/EX-002-regulatory-retrieval.md`
- Results: this document
- Raw retrieval runs: `artifacts/experiments/EX-002/retrieval_runs.jsonl`
- Metrics: `artifacts/experiments/EX-002/metrics.json`
- Latency: `artifacts/experiments/EX-002/latency.json`
- Metadata audit: `artifacts/experiments/EX-002/metadata_audit.json`

