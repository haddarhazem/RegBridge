# EX-024-R1 — Corrected evidence-constrained extraction results

## Protocol

EX-024-R1 reused the unchanged 15-document, 105-annotation benchmark and the same `mistral-small-latest` model. Only instrumentation and the V2/V3 evidence contract changed: source paragraphs were exposed as allowlisted `SRC-###` IDs; the backend resolved IDs to exact locators; V3 extraction and verification were accounted for separately. No semantic case-specific tuning or gold-label changes were made.

Utility gates were frozen before this run: recall >= 0.70, usable/conclusive rate >= 0.90, structured validity >= 0.90 for structured candidates, and provenance >= 0.95 for V2/V3. Safety gates remained zero privacy leakage, zero critical unsupported claims, zero accepted numeric mutations, zero negation reversals, and zero invalid evidence accepted.

## Metrics

| Metric | V0 | V1 | V2 | V3 |
|---|---:|---:|---:|---:|
| Provider success | 15/15 | 15/15 | 12/15 | 11/15 |
| Parse/structured validity | 0/15 | 14/15 | 12/15 | 11/15 |
| Usable/conclusive rate | 0/15 | 14/15 | 12/15 | 11/15 |
| Claim precision | 0/0 | 47/108 | 38/81 | 23/47 |
| Unsupported claim rate | 0/0 | 61/108 | 43/81 | 24/47 |
| Extraction recall | 0/90 | 47/90 | 38/90 | 23/90 |
| Evidence-ref validity | N/A | N/A | 56/81 | 58/64 |
| Evidence entailment precision | N/A | N/A | 23/56 | 23/47 |
| Provenance coverage | N/A | N/A | 23/38 | 23/23 |
| Critical unsupported claims | 0 | 21 | 13 | 8 |
| Numeric mutations | 0 | 6 | 4 | 3 |
| Negation errors | not separately emitted | not separately emitted | not separately emitted | not separately emitted |
| Abstention / UNVERIFIABLE | N/A | N/A | N/A | 16/64 |
| Average latency | 1179 ms | 1971 ms | 2216 ms | 4053 ms |
| Input tokens | 2959 | 2779 | 2556 | 2276 |
| Output tokens | 1636 | 3865 | 4634 | 3955 |

V0 had 15/15 provider successes but 0/15 parseable outputs; this is an operational usability failure, not evidence of safe semantic extraction. V2 evidence IDs materially improved syntactic reference validity over the initial 0/84 diagnostic, but evidence entailment remained low and critical unsupported claims remained non-zero. V3 had 15 extraction calls, 58 verifier calls, 53 verifier provider successes, 53 structured verifier results, 47 SUPPORTED verdicts, 1 UNSUPPORTED verdict and 16 UNVERIFIABLE decisions; the final claims still contained 8 critical unsupported claims and failed the gate.

## Critical cases

The frozen cases include numeric mutation cases R209-001, R209-002, R209-003, R209-005, R209-008, R209-011, R209-012, R209-013 and R209-015; causality cases R209-004 and R209-010; scope cases R209-003, R209-005, R209-012 and R209-014; and TRL/IP/commercialization absence cases R209-002, R209-004, R209-005, R209-007, R209-009 and R209-012. These were not removed or relabeled.

## Decision

NONE. No candidate satisfies the critical safety gate or the utility floors. V3's abstention behavior is safer than accepting unsupported claims, but its recall and critical-claim metrics are not production-usable. No production extraction API, persistence model or migration is implemented.
