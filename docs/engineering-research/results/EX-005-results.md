# EX-005 results — Project fact inference

## Benchmark

24 synthetic cases: 16 development and 8 independent holdout. Domains were `activity`, `sector`, `technology`, `data`, `market`, and `location`. The benchmark contains no private data and no candidate-generated labels.

## EX-005A — Development evaluation

The initial V1 provider call returned valid JSON with the wrong fact shape. That attempt is preserved separately; structured-output validity was 6.25%. The provider request was corrected to use an explicit JSON schema through `LLMProvider`; the corrected V1 run had 100% structured-output validity.

| Metric | V0 initial | V0 corrected | V1 corrected |
|---|---:|---:|---:|
| Precision | 75.93% | 98.31% | 17.02% |
| Recall | 63.08% | 89.23% | 12.31% |
| F1 | 68.91% | 93.55% | 14.29% |
| Unsupported-inference rate | 24.07% | 1.69% | 82.98% |
| Provenance correctness | 96.30% | 94.92% | 100.00% |
| Ambiguity preservation | 0.00% | 62.50% | 25.00% |
| Structured-output validity | 100.00% | 100.00% | 100.00% |

Development corrections were limited to observed deterministic failures: explicit negation, context-specific data absence, and unresolved “to be defined” wording. No holdout case was inspected for tuning.

## EX-005B — Independent holdout

| Metric | V0 corrected | V1 structured LLM |
|---|---:|---:|
| Precision | 82.61% | 23.81% |
| Recall | 59.38% | 15.63% |
| F1 | 69.09% | 18.87% |
| Unsupported-inference rate | 17.39% | 76.19% |
| Provenance correctness | 100.00% | 100.00% |
| Ambiguity preservation | 25.00% | 25.00% |
| Structured-output validity | 100.00% | 100.00% |
| Latency median / p95 | <1 ms / <1 ms | 1,432.6 ms / 1,682.4 ms |
| Token usage | none | 1,002 prompt / 1,624 completion / 2,626 total |

No monetary cost was estimated.

## Decision

**Selected strategy: V0 corrected deterministic extraction.**

V0 is the safer candidate under the frozen primary priority: it has materially higher precision and much lower unsupported-inference rate on the untouched holdout. V1’s structured validity and provenance fields were technically reliable after the schema correction, but its semantic precision was unacceptable for silently creating project facts. A missed fact can be requested or confirmed later; a fabricated fact could contaminate regulatory analysis.

Hybrid required: **NO**. The measured result does not justify adding a second inference mechanism.

## Production implications

Production uses the conservative deterministic extractor only. Facts are stored as explicit `project_facts` records with categorical uncertainty, bounded provenance, origin, and confirmation status. Only `confirmed` and `corrected` facts are projected into authorized AI context. Pending inferred facts remain visible for user review but cannot silently override project context.

## Limitations

- 24 synthetic descriptions are not a universal accuracy estimate.
- Matching uses exact annotated domain/value pairs; broader semantic equivalence was not claimed.
- V1 results depend on one configured Mistral model and one frozen prompt/schema.
- PostgreSQL migration and persistence validation could not be completed because the local Docker PostgreSQL daemon became unavailable; no success was fabricated.
- No protected attributes, private documents, or production/customer data were used.
