# EX-024-R2 — Extractive grounding results

## History and protocol

EX-024-R2 reused RQ-024 and introduced the frozen hypothesis H-024-R2: selecting exact source segments instead of generating factual values should reduce mutations and unsupported claims. The holdout contains 12 fresh controlled excerpts and 96 field annotations. It was frozen before provider execution and stored at `benchmarks/research_extraction_ex024_r2_holdout_v1.json`.

The requested balance target was only partially achieved: explicit applications and keywords have 6 supported/6 absent; technologies have 9/3; main results 10/2; limitations 11/1; domains 12/0; research problem 11/1; methodology 11/1. This imbalance is recorded as a limitation and means R2 is not a definitive negative-field evaluation for every field.

The final immutable run is `20260825T151411Z` under the ignored local path `artifacts/experiments/ex024/r2/20260825T151411Z/results.json`. The earlier R2 run remains preserved under its own run ID. The artifact overwrite guard refuses an existing completed run ID.

## Metrics

| Metric | V0 | V1 | V2 | V3 | V4 |
|---|---:|---:|---:|---:|---:|
| Provider success | 12/12 | 12/12 | 12/12 | 10/12 | 0/12 |
| Parse/structured validity | 0/12 | 12/12 | 12/12 | 10/12 | 0/12 |
| Usable/conclusive rate | 0/12 | 12/12 | 12/12 | 10/12 | 0/12 |
| Claim precision | 0/0 | 16/110 | 6/104 | 2/81 | 0/0 |
| Unsupported claim rate | 0/0 | 94/110 | 98/104 | 79/81 | 0/0 |
| Extraction recall | 0/76 | 16/76 | 6/76 | 2/76 | 0/76 |
| Explicit application accuracy | 6/12 | 6/12 | 6/12 | 6/12 | 6/12 |
| Critical unsupported claims | 0 | 25 | 25 | 20 | 0 |
| Numeric mutations | 0 | 5 | 7 | 6 | 0 |
| Negation errors | 0 | 0 | 0 | 0 | 0 |
| Evidence-ref validity | N/A | N/A | 104/104 | 90/90 | N/A |
| Evidence entailment precision | N/A | N/A | 6/104 | 2/90 | N/A |
| Provenance coverage | N/A | N/A | 6/6 | 2/2 | N/A |
| Exact-copy integrity | N/A | N/A | N/A | N/A | N/A |
| Abstract provenance | N/A | N/A | N/A | N/A | N/A |
| Average latency | 1233 ms | 1765 ms | 2727 ms | 7090 ms | 133 ms |
| Input tokens | 3802 | 3658 | 3958 | 3288 | N/A |
| Output tokens | 1547 | 2995 | 4622 | 3814 | N/A |

V4 had 0/12 provider successes because the configured provider became unavailable during the V4 stage. Its exact-copy and abstract metrics are therefore N/A, not passing zeroes. The V4 controlled-stub tests passed the no-factual-value contract, but that is not a live holdout result.

## Field-level results

The values below are TP/FP/FN for each field:

| Field | V0 | V1 | V2 | V3 | V4 |
|---|---|---|---|---|---|
| domains | 0/0/12 | 0/17/12 | 0/13/12 | 0/12/12 | 0/0/12 |
| technologies | 0/0/9 | 0/12/9 | 0/11/9 | 0/8/9 | 0/0/9 |
| research_problem | 0/0/11 | 4/8/7 | 1/12/10 | 0/8/11 | 0/0/11 |
| methodology | 0/0/11 | 4/14/7 | 2/13/9 | 0/11/11 | 0/0/11 |
| main_results | 0/0/10 | 4/7/6 | 2/8/8 | 1/7/9 | 0/0/10 |
| explicit_applications | 0/0/6 | 0/6/6 | 0/6/6 | 0/5/6 | 0/0/6 |
| keywords | 0/0/6 | 0/12/6 | 0/12/6 | 0/10/6 | 0/0/6 |
| limitations | 0/0/11 | 4/18/7 | 1/23/10 | 1/18/10 | 0/0/11 |

## V4 error analysis

Provider failures: 12/12. Wrong-field selections, missed source segments and abstract defects were not observable in live V4 because no provider response was received. Controlled tests verified exact-copy behavior, version-scoped IDs, rejection of factual `value` fields, and deterministic abstract construction.

## Decision

NONE. V0–V3 fail safety and utility gates. V4 was not empirically evaluated because the provider was unavailable for every V4 call; it cannot be selected from stub results. No production extraction persistence or API was created.
