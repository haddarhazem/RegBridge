# EX-024 — Evidence-constrained research extraction results

## Execution

The frozen benchmark `research-extraction-ex024-v1` contains 15 controlled synthetic excerpts and 105 annotated field instances, including 90 supported gold values and explicit absent/UNKNOWN fields. The benchmark and locator policy were frozen before the final run. All candidates used `mistral-small-latest`, temperature 0, the same source excerpts, prompt version `ex024-v1`, and schema version `research-extraction-schema-v1`.

The first network attempt was unavailable. After the configured network path was authorized, the final run completed with provider failures retained in the rows. No source text is stored in this result artifact.

## Metrics

| Metric | V0 | V1 | V2 | V3 |
|---|---:|---:|---:|---:|
| Evidence precision | 0/0 | 30/64 (0.4688) | 34/84 (0.4048) | 0/0 |
| Unsupported claim rate | 0/0 | 34/64 (0.5313) | 50/84 (0.5952) | 0/0 |
| Extraction recall | 0/90 (0.0000) | 30/90 (0.3333) | 34/90 (0.3778) | 0/90 (0.0000) |
| Provenance coverage | N/A | N/A | 0/84 (0.0000) | N/A |
| Structured validity | 0/15 (0.0000) | 9/15 (0.6000) | 14/15 (0.9333) | 11/15 (0.7333) |
| Explicit application accuracy | 7/15 (0.4667) | 10/15 (0.6667) | 11/15 (0.7333) | 7/15 (0.4667) |
| Critical unsupported claims | 0 | 7 | 14 | 0 |
| Numeric mutations | 0 | 2 | 6 | 0 |
| Negation errors | 0 | 0 | 0 | 0 |
| Provider success | 9/15 (0.6000) | 10/15 (0.6667) | 14/15 (0.9333) | 11/15 (0.7333) |
| Average latency | 1232.27 ms | 1923.87 ms | 3515.12 ms | 6505.81 ms |
| Input tokens | 1386 | 1386 | 2294 | 1787 |
| Output tokens | 1177 | 2509 | 8544 | 6442 |
| Cost | unavailable | unavailable | unavailable | unavailable |

Denominators are shown explicitly. V0 provider successes were not trustworthy structured outputs: all 15 loose responses failed the JSON/normalization contract. V3's zero generated-claim denominator reflects bounded extraction/verifier failures, not a successful safe extraction.

## Error analysis

- V0: loose responses were not safely machine-readable; they were rejected rather than persisted as trusted facts.
- V1: unsupported critical claims and numeric mutations remained; structure alone did not prevent false passes.
- V2: the structured contract was mostly valid, but evidence locators were rejected when they did not resolve to the exact deterministic paragraph locator. It also produced unsupported claims and numeric mutations.
- V3: separate verification incurred the highest latency and had provider/structured failures; the run did not produce a usable accepted extraction. It therefore cannot be credited as a safety win.
- Representative traps covered by the frozen benchmark include invented applications, technology inference, numeric mutation, correlation/causality, mice/human scope, commercialization/TRL/IP absence, explicit limitations, mixed claims, negation, and absent fields.

## Gate conclusion

No candidate satisfies the production gate. V1 and V2 have non-zero critical unsupported claims. V0 and V3 have no accepted generated claims because their outputs failed bounded parsing or provider/verifier execution. This is a valid negative result; no candidate is selected and no production extraction path is activated.

The observed V2 provenance failures also identify a protocol/implementation follow-up: production evidence locators must be generated and validated against the exact source parser, not accepted from unconstrained model text. That follow-up cannot be silently converted into a production selection in SCRUM-209.
