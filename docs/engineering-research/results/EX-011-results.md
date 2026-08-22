# EX-011 results — Contract evidence resolution and semantic verification

## Execution

- Provider: Mistral production provider
- Model: `mistral-small-latest`
- Prompt: `scrum193-ex011-verification-v1`
- Benchmark: `contract_verification_ex011_v1`
- Attempts: 2; attempt 2 is the recorded result after correcting bounded
  reason-code validation and semantic verifier instructions.
- Data: synthetic contracts only

## Evidence resolution

The old real-provider SCRUM-193 check accepted only 3/8 responses with valid
model-supplied offsets (37.5%). In EX-011, the model supplied quotes and the
application derived offsets deterministically:

| Split | Resolved | Ambiguous | Invalid |
|---|---:|---:|---:|
| Development | 12/12 | 0 | 0 |
| Holdout | 8/8 | 0 | 0 |
| Adversarial | 8/8 | 0 | 0 |

This fixes the location-generation failure in the tested synthetic set, but
does not establish semantic support.

## Candidate metrics

False-support rate is the primary metric: unsupported or uncertain claims
accepted as `SUPPORTED`, divided by all claims that should not be supported.

| Candidate / split | False support | Supported precision | Supported recall | False-block rate | Pass rate |
|---|---:|---:|---:|---:|---:|
| V2-A development | 100% | 58.33% | 100% | 0% | 58.33% |
| V2-A holdout | 100% | 12.5% | 100% | 0% | 12.5% |
| V2-A adversarial | 100% | 12.5% | 100% | 0% | 12.5% |
| V2-B development | 60% | 70% | 100% | 0% | 75% |
| V2-B holdout | 14.29% | 50% | 100% | 0% | 87.5% |
| V2-B adversarial | 42.86% | 25% | 100% | 0% | 50% |

The verifier materially improves holdout false support, but adversarial false
support remains material. It does not meet the production safety gate.

## Latency and tokens

Measured real calls, medians and p95 values in milliseconds:

| Split | Extraction median/p95 | Verifier median/p95 |
|---|---:|---:|
| Development | 1258 / 2619 | 1063 / 1339 |
| Holdout | 1191 / 1463 | 1112 / 1203 |
| Adversarial | 1287 / 1716 | 1026 / 1232 |

Attempt 2 consumed 3,843 prompt tokens and 1,629 completion tokens for
extraction, plus 6,785 prompt tokens and 1,070 completion tokens for
verification. Cost was not calculated.

## Decision

Select the quote-based deterministic resolver as the evidence-location design.
Do not select V2-B as a production semantic verifier yet: its same-model
adversarial false-support rate is 42.86%. No production `ContractFindingVerifier`
was added. A follow-up experiment is required before introducing semantic
verification into the production path, preferably with stronger adversarial
coverage and consideration of an independently evaluated verifier model.

Evidence strength: **MODERATE** for deterministic quote resolution and
**WEAK** for production semantic verification.
