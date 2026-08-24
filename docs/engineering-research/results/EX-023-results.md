# EX-023 results — Investor Opportunity Brief factuality verification

## Frozen evaluation

Benchmark: `investor_opportunity_brief_ex023_v1` (24 synthetic claims).

### V0 deterministic rules

| Metric | Result |
|---|---:|
| Unsupported-claim recall | 100% |
| Verification precision | 100% |
| False-pass rate | 0% |
| False-block rate | 10% |
| Macro F1 | 94.74% |
| UNKNOWN protection | PASS |
| Matching-fidelity protection | PASS |
| Unauthorized-data usage | 0 |

The only false block was the faithful natural-language paraphrase case. Exact
numeric formatting was handled deterministically. All unsupported critical
claims, including financial predictions, customers, traction, partnerships,
IP, and mutated matching outcomes, were rejected.

### Provider diagnosis

The initial blocked run was caused by the execution sandbox denying outbound
network connections (`PermissionError`, WinError 5) beneath the bounded
`LLMProviderUnavailableError`. Settings, credentials, model, SDK and native
JSON_SCHEMA were valid. The same minimal request succeeded with network access
enabled, so no provider/configuration workaround was required.

### V1 semantic verifier

V1 made 24 provider calls. All calls reached Mistral; 16 returned valid bounded
structured verdicts and 8 were rejected as invalid structured responses. No
provider call was treated as a supported verdict. No critical unsupported
claim passed. Provider success was 24/24, structured-output reliability was
16/24 (66.67%), invalid structured-output rate was 8/24 (33.33%), and the
end-to-end conclusive verdict rate was 16/24 (66.67%). Invalid outputs were
treated operationally as rejected/no verdict.

| Metric | V1 |
|---|---:|
| Unsupported-claim recall | 100% |
| Precision | 100% |
| False-pass rate | 0% |
| False-block rate | 0% |
| Critical false passes | 0 |
| Average / p95 latency | 829.8 / 1,235.5 ms |
| Input / output tokens | 3,914 / 833 |

### V2 hybrid verifier

V2 resolved 23/24 cases deterministically and used one semantic fallback for
the faithful paraphrase. The fallback returned `SUPPORTED` with an authorized
evidence reference.

| Metric | V2 |
|---|---:|
| Unsupported-claim recall | 100% |
| Precision | 100% |
| False-pass rate | 0% |
| False-block rate | 0% |
| Critical false passes | 0 |
| Semantic fallback calls | 1 |
| Average / p95 latency | 662.5 / 662.5 ms |
| Input / output tokens | 177 / 36 |
| Calls avoided vs V1 | 23 |

## Decision

Select V2 deterministic-first hybrid verification for SCRUM-205. It preserved
the zero critical false-pass gate and matching/UNKNOWN protections while
resolving the one faithful paraphrase with one semantic call instead of 24.
Provider failure remains fail-closed: the unresolved claim stays
`UNVERIFIABLE` and the verification run cannot become `VERIFIED`.

Evidence strength: MODERATE. The benchmark is frozen and controlled but small;
the live result used the configured Mistral model and should receive a fresh
holdout before any future model/provider change.

## EX-023-S1 supplementary holdout

The separate 10-case holdout was frozen before provider execution. V0 resolved
0 cases as SUPPORTED, 5 as UNSUPPORTED and 5 as UNVERIFIABLE. V1 made 10
calls, with 7 valid structured outputs and 3 invalid outputs rejected without a
verdict. Of the five supported paraphrases, four were accepted and S1-02 was
returned as UNSUPPORTED; all three invalid outputs were on unsupported cases.

V2 resolved five adversarial cases deterministically and called Mistral for
the five unresolved paraphrases. All five semantic calls returned valid
structured outputs. All five paraphrases were accepted as SUPPORTED. V2 made
five calls instead of V1's ten and had zero critical false passes or false
blocks on the fresh holdout.

| Metric | V0 | V1 | V2 |
|---|---:|---:|---:|
| Supported paraphrases correctly resolved | 0/5 | 4/5 valid/conclusive | 5/5 |
| Unsupported recall | 100% | 100% | 100% |
| Precision | 100% | 100% valid outputs | 100% |
| False-pass rate | 0% | 0% | 0% |
| False-block rate | 100% | 20% end-to-end | 0% |
| Critical false passes | 0 | 0 | 0 |
| Provider calls | 0 | 10 | 5 |
| Deterministic-only resolutions | 10 | 0 | 5 |
| Semantic fallback average | n/a | 662.8 ms | 625.4 ms |
| Overall per-case average | 0.09 ms | 662.8 ms | 312.7 ms* |
| Input / output tokens | 0 / 0 | 1,702 / 376 | 889 / 178 |

Invalid semantic outputs are rejected as no verdict; they never become
SUPPORTED. The V1 valid-output quality figures are conditional and do not
hide its three end-to-end no-verdict cases. V2's five deterministic-only
resolutions avoided five provider calls and produced conclusive results for
all ten cases.

For V1, the runner's historical `macro_f1` field is actually the
positive-class F1 calculation. It is reported here as positive-class F1
(88.89%), not macro F1. The conventional two-class macro F1 for the seven
conclusive V1 outputs is 84.44% when calculated on valid outputs only;
unresolved outputs remain explicitly reported in the end-to-end metrics.

### EX-023-S1 metric audit

The initial S1 report was stale: it described a prior stochastic run (V1 5/5
and V2 4/5) rather than the persisted latest result. The frozen benchmark and
labels were unchanged. The latest persisted rows show V1 S1-02 as a valid
`UNSUPPORTED` false block, three invalid structured outputs (S1-06, S1-09,
S1-10), and V2 S1-01 through S1-05 as valid `SUPPORTED` semantic results.

The persisted V2 `overall_avg_latency_ms` value of 208.5 ms is not a valid
10-case average: the runner included deterministic timings for all ten cases
and semantic timings for the five fallback cases, producing a 15-sample
average. Using the persisted group means and the five/five case split, the
correct intended per-case average is approximately 312.7 ms. Case-level
timings and total benchmark wall-clock time were not persisted, so an exact
raw-timing recomputation is not possible from the artifact alone.

*The corrected overall V2 average is derived from the persisted group means;
the experiment runner was not changed or rerun during this audit.*
