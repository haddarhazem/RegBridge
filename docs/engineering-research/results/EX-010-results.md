# EX-010 results - RQ-011

## Artifacts

- Core benchmark: `benchmarks/contract_extraction_ex010_v1.json`
- Development: 12 cases
- Holdout: 8 cases
- Adversarial benchmark: `benchmarks/contract_extraction_ex010_adversarial_v1.json` (8 cases)
- Raw results: `artifacts/experiments/ex010_contract_extraction_results.json`

Percentages below are derived from the raw result artifact.

## V0 - Direct prompting

| Metric | Development | Holdout | Adversarial |
|---|---:|---:|---:|
| Precision | 100% | 57.14% | 66.67% |
| Recall | 84.62% | 80% | 100% |
| F1 | 91.67% | 66.67% | 80% |
| Unsupported finding rate | 0% | 42.86% | 33.33% |
| Type correctness | 81.82% | 42.86% | 33.33% |
| Evidence accuracy | 0% | 0% | 0% |
| Structured validity | 0% | 0% | 0% |
| Latency/tokens | deterministic / unavailable | deterministic / unavailable | deterministic / unavailable |

## V1 - Structured extraction

| Metric | Development | Holdout | Adversarial |
|---|---:|---:|---:|
| Precision | 100% | 57.14% | 66.67% |
| Recall | 84.62% | 80% | 100% |
| F1 | 91.67% | 66.67% | 80% |
| Unsupported finding rate | 0% | 42.86% | 33.33% |
| Type correctness | 100% | 42.86% | 55.56% |
| Evidence accuracy | 0% | 0% | 0% |
| Structured validity | 100% | 100% | 100% |
| Latency/tokens | deterministic / unavailable | deterministic / unavailable | deterministic / unavailable |

## V2 - Structured extraction + evidence

| Metric | Development | Holdout | Adversarial |
|---|---:|---:|---:|
| Precision | 100% | 80% | 85.71% |
| Recall | 84.62% | 80% | 100% |
| F1 | 91.67% | 80% | 92.31% |
| Unsupported finding rate | 0% | 20% | 14.29% |
| Type correctness | 100% | 60% | 71.43% |
| Evidence accuracy | 90.91% | 75% | 83.33% |
| Exact span validity | 100% | 100% | 100% |
| Structured validity | 100% | 100% | 100% |
| Latency/tokens | deterministic / unavailable | deterministic / unavailable | deterministic / unavailable |

V2 reduces unsupported findings on untouched holdout and adversarial cases
relative to V0/V1 and provides reproducible evidence spans. It does lose some
recall on the development set where conflicting clauses are represented as one
uncertain expected finding but are emitted as separate clause observations.

## Evaluator validation

The evaluator detected invented findings, wrong categories, wrong types,
unrelated evidence, quote/offset mismatches, negation errors, wrong document
versions and missing expected findings.

## Decision

Select V2 - structured extraction with mandatory evidence references to an
immutable `DocumentVersion`. Evidence that cannot resolve exactly is not
presented as grounded. Findings, risks, recommendations and uncertainty remain
explicitly distinct.

No separate verifier is justified by this experiment. Deterministic validation
is the selected safety gate; a further semantic verifier requires a separate
experiment.

Evidence strength: MODERATE. The strategy comparison is reproducible, but the
corpus is synthetic and the common harness is not a real provider evaluation.
