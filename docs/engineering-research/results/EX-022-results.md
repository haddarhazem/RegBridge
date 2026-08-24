# EX-022 results

## Phase 1 — original V1 contract

V0 deterministic generation passed all 10 cases. It produced the required
structured content, preserved MATCH/MISMATCH/UNKNOWN outcomes, derived missing
information from the evidence bundle, used the deterministic disclaimer, and
produced zero unsupported claims, safety violations, or unauthorized-data
usage.

The live V1 run used Mistral `mistral-small-latest` on the same 10 synthetic
bundles. All 10 provider calls returned successfully with native JSON_SCHEMA
responses, but the existing SCRUM-204 acceptance gate rejected all 10: 10 had
matching-fidelity failures and 3 also contained unsupported evidence
references. Every rejected output used the deterministic fallback. No unsafe
output was accepted. Average latency was approximately 1,759 ms; input tokens
were 2,470 and output tokens were 2,286; cost was unavailable.

The result was not evidence that Mistral failed structurally. JSON_SCHEMA was
valid, but the generation contract and validator expectation were mismatched:
the schema accepted free-form thesis-fit text while the validator searched
that prose for canonical matching literals. This phase is therefore not
trustworthy evidence for a semantic-failure conclusion.

## Phase 2 — corrected-contract V1

The corrected contract adds five typed `matching_acknowledgements` entries,
each carrying the canonical dimension and outcome, and typed highlights whose
evidence references are restricted to the bundle allowlist. Validation now
compares the structured acknowledgements with the canonical matching result;
natural-language literal matching was removed. Rejected parsed outputs and
rejected evidence references are retained in the generated evaluation
artifact, without secrets or private unrelated data.

The corrected V1 runner was previously invoked with `EX022_LIVE=1`, but the
provider was unavailable before parsed output was received. A subsequent
development smoke confirmed that Settings loads the local credential and the
provider can be instantiated, but the live Mistral request still failed with
the bounded `LLMProviderUnavailableError`. Per protocol, the 10-case live
holdout was not rerun after that smoke failure. This is a provider-availability
result, not a corrected-contract quality result.

The corrected runner now reports provider metrics separately from fallback
metrics: provider API successes, structured responses, provider JSON_SCHEMA
validity, provider semantic-validator passes, accepted V1 outputs, fallback
outputs, and fallback schema validity.

## Metrics

| Metric | V0 | V1 accepted output |
|---|---:|---:|
| Cases | 10 | 10 |
| Section completeness | 10/10 | 10/10 raw |
| Unsupported claims | 0 | 3 raw rejected cases |
| Missing-information correctness | 10/10 | fallback preserved |
| Matching fidelity | 10/10 | 0/10 accepted; all rejected |
| Safety violations | 0 | 0 accepted |
| Unauthorized data usage | 0 | 0 |
| JSON_SCHEMA validity | n/a | 10/10 |

## Decision

Select V0 deterministic template generation for the SCRUM-204 production
brief. Keep the corrected V1 JSON_SCHEMA path in research/tests until a live
evaluation with credentials and a fresh controlled result earns a future gate;
retain the deterministic fallback. The brief remains DRAFT/UNVERIFIED;
SCRUM-205 owns the dedicated factual verification layer.
