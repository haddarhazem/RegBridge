# EX-002 - Regulatory retrieval on the frozen Qdrant corpus

## Jira

SCRUM-184

## Research Question

RQ-002: Given the currently available frozen French regulatory corpus in
Qdrant, which retrieval configuration retrieves the most useful expected
official evidence while keeping latency and retrieval complexity reasonable?

## Status

EXECUTED - dense metrics completed; reranking gate was justified but the
single CPU reranker attempt did not complete within the available execution
window.

## Corpus

The read-only collection is `reglementation_chunks`. The observed snapshot is
recorded in `benchmarks/manifests/regulatory_qdrant_snapshot_v1.json`:

- 47,881 points and 45,982 indexed vectors;
- 2 segments;
- 1024-dimensional cosine vectors;
- HNSW `m=16`, `ef_construct=100`;
- payloads on disk, no quantization, strict mode enabled;
- observed payload keys: `source_domain`, `url`, `parent_url`, `chunk_index`,
  `content`.

The collection was inspected using metadata, count, scroll, and query reads
only. No points, payloads, indexes, or collection settings were changed.

## Corpus Freeze Constraint

The collection is the only reproducible corpus snapshot. Original source
pages and the historical ingestion pipeline were not recovered. No deletion,
upsert, index creation, configuration change, re-embedding, rechunking, or
scraping is permitted.

## Historical Evidence

No reproducible prior retrieval comparison or ingestion configuration was
found. Historical team observations, if any, must be treated as prior
engineering evidence and not as an EX-002 result.

## Hypothesis

The existing BGE-M3 dense representation is expected to retrieve relevant
official evidence for many regulatory questions, while top-k will trade
precision against evidence coverage. A reranker may improve ordering only if
relevant evidence is already present in a larger candidate set but ranked too
low.

## Controlled Variables

- frozen collection and stored chunks;
- stored vectors and BGE-M3 1024-dimensional representation;
- cosine distance;
- benchmark questions and human annotations;
- explicit local BGE-M3 query encoder;
- fixed Qdrant query parameters;
- CPU environment.

## Independent Variable

Initial comparison: `k = 3`, `k = 5`, and `k = 10`. Only top-k may vary in the
first comparison.

## Deferred Variables

Chunk-size and overlap evaluation is deferred until the original raw corpus or
an equivalent reproducible source snapshot becomes available. Existing chunk
boundaries are fixed; stored chunks must not be merged or split for this
experiment. New embedding models, hybrid retrieval, and sparse reindexing are
also deferred.

## Benchmark and Human Annotation Gate

`benchmarks/regulatory_retrieval_v1.jsonl` contains 25 questions, of which 20
are `human_validated` with deterministic point-ID evidence and five remain
pending. Only the 20 human-validated questions were used for final metrics.

The read-only helper generated ten candidate evidence rows for `REG-001` under
the ignored artifact path `artifacts/experiments/EX-002/annotation_candidates.jsonl`.
Those candidates are a human-review worksheet only; no relevance label was
assigned automatically.

## Metrics

Definitions are fixed before measurement:

- Recall@k: matched expected evidence items retrieved in the first k divided
  by the number of expected evidence items;
- Precision@k: matched retrieved items in the first k divided by k;
- MRR: reciprocal rank of the first deterministically matched item;
- evidence coverage: fraction of benchmark questions with at least one matched
  expected item;
- latency: embedding, Qdrant, and combined pipeline median/p95 using a warm-up
  and monotonic high-resolution timer.

Matching prefers exact human-provided `point_id`; otherwise it uses the
provided source/domain/URL/parent/chunk locators. Embedding similarity is not
used as a relevance judge.

## Metadata / Provenance Audit

A read-only sample of 100 points had 100% presence for `source_domain`,
`url`, `parent_url`, `chunk_index`, and `content`. The payload schema was
reported empty. Organization, title, and date were not present as structured
payload fields; they may sometimes be inferred from Markdown or URLs, but no
deterministic extraction is claimed by this gate.

## Reranking Gate

Not executed. Reranking will only be considered after the dense benchmark is
human-validated and shows strong recall with materially weak first-rank
ordering or excessive top-k noise. It is not a production dependency here.

## Hybrid Retrieval

Deferred because the frozen collection exposes one dense 1024-dimensional
vector and no reproducible sparse representation was found. Rebuilding the
corpus is outside this research constraint.

## Reproduction Commands

```powershell
python -m pip install -e ".[test,research]"
python -m pytest experiments/retrieval/ex002_regulatory_retrieval/tests -q
python -m experiments.retrieval.ex002_regulatory_retrieval --limit 10
```

The live helper requires configured local Qdrant credentials and a local or
cached BGE-M3 model. It does not print credentials or mutate Qdrant.

## Limitations

The corpus is frozen and its original raw source pages and chunking process
are unavailable. The benchmark is currently small and unvalidated. The query
encoder is an explicit compatibility implementation rather than recovered
historical ingestion code. Qdrant network latency may vary, and all evidence
applies only to the observed collection snapshot.
