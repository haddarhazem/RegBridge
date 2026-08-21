# EX-002 - Regulatory retrieval on the frozen Qdrant corpus

This is the SCRUM-184 research gate for RQ-002. The experiment is currently
`ANNOTATION_PENDING`; it must not produce final retrieval metrics until at
least 20 useful questions have been human-validated.

The only corpus is the read-only `reglementation_chunks` collection. The
reader intentionally exposes metadata, count, scroll, retrieve, and query
operations only. It has no mutation methods and must not be extended with
upsert, delete, payload-index, collection-update, or recreate operations.

The historical ingestion implementation was not found in the repository. The
helper therefore uses an explicit local BGE-M3 mean-pooling, normalized query
encoder and does not claim exact ingestion reproduction. BGE-M3 query vectors
must be 1024-dimensional.

Run unit tests without Qdrant:

```powershell
python -m pytest experiments/retrieval/ex002_regulatory_retrieval/tests -q
```

Generate a read-only candidate worksheet after configuring local Qdrant and
the cached BGE-M3 model:

```powershell
python -m experiments.retrieval.ex002_regulatory_retrieval --limit 10
```

The output is for human annotation only. The helper never assigns
`human_validated` labels.
