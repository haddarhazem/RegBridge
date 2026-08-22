# EX-003 — Response verification results

## Status

EXECUTED — V0, V1, and V2 completed on the frozen human-validated set.
Attempt 1 preserved the controlled V2 provider failure; Attempt 2 completed
all 24 structured V2 calls after the response-format transport correction.

SCRUM-185 remains a research result, not a production verifier decision.
RD-004 has not been created.

## Frozen evaluation set

- Primary: 24 human-validated real-evidence cases: VER-004–VER-009,
  VER-011–VER-019, VER-021–VER-029.
- Reserved real-evidence cases: VER-001, VER-002, VER-003, VER-010, VER-020.
- Synthetic safety sanity fixture: VER-030, excluded from all primary metrics.
- Human gate: PASS (24 / 24 required minimum).

The benchmark labels were written before execution and were not tuned after
observing results. V2 received the leakage-safe projection containing only
question, answer, claims, evidence, and provenance. Expected labels, category,
mutation type, and annotation metadata were excluded.

## Variants

### V0 — no verifier

Every answer returns `pass`.

### V1 — deterministic evidence rules

Checks evidence presence, duplicate IDs, citation resolution, and public-source
membership in the supplied evidence package. It does not evaluate semantic
claim entailment.

### V2 — Mistral-assisted verifier

Uses the provider-neutral LLM contract, the pre-registered V2 prompt, bounded
JSON output, and the configured Mistral provider. A deterministic bounded
excerpt projection was used to remain within the existing 12,000-character
provider message contract. This did not change benchmark evidence or labels.

## Results

### Primary metrics

| Metric | V0 | V1 | V2 |
|---|---:|---:|---:|
| Samples | 24 | 24 | 24 attempted |
| Successful predictions | 24 | 24 | 0 |
| Failed predictions | 0 | 0 | 24 |
| Unsupported/contradicted claim rate among allowed responses | 0.4118 | 0.4167 | not available |
| Public-source attribution correctness | 0.7500 | 0.7500 | not available |
| Citation/evidence coverage | 0.0000 | 0.0000 | not available |
| False-pass rate | 1.0000 | 0.6250 | not available |
| False-block rate | 0.0000 | 0.0000 | not available |

The unsupported-claim rate is calculated only over human material claims in
cases the variant allowed. Public-source correctness is the frozen human
attribution property for the selected set; it is reported separately from
structural citation resolution.

### Verdict confusion matrices

V0:

```text
expected pass              -> pass: 5
expected pass_with_warnings-> pass: 3
expected block             -> pass: 16
```

V1:

```text
expected pass              -> pass: 5
expected pass_with_warnings-> pass: 3
expected block             -> pass: 10, block: 6
```

V1 blocked: VER-016, VER-017, VER-018, VER-019, VER-028, VER-029.
It did not block semantic unsupported/contradicted claims because semantic
entailment is outside deterministic V1.

V2 has no confusion matrix because no structured prediction succeeded.

### Latency

Measured with a monotonic timer over the variant invocation:

| Variant | Median ms | p95 ms | Sample note |
|---|---:|---:|---|
| V0 | 0.0034 | 0.0138 | 24 successful local predictions |
| V1 | 0.0046 | 0.0078 | 24 successful local predictions |
| V2 | 8.1607 | 10.3960 | failure time only; not usable verifier latency |

V2 token usage was unavailable because no provider response succeeded. Cost is
`not reliably attributed`; no pricing was fabricated.

## Representative error analysis

- V0 false passes all 16 human-expected `block` cases, confirming the value of
  retaining the no-verifier baseline.
- V1 catches structural source/citation failures in the wrong-citation and
  mixed cases, but passes semantic contradiction and unsupported-claim cases.
- VER-017 and VER-019 confirm the separation between semantic support and
  citation resolution: their claims can be supported while their candidate
  citation IDs fail to resolve.
- VER-028 and VER-029 contain mixed claims; V1 catches only structural source
  defects and cannot judge the unsupported material claims.
- V2’s failure is an operational/provider availability result, not evidence
  that model-assisted verification is good or bad. The provider adapter
  intentionally exposes only the controlled failure class and does not print
  credentials or provider secrets.

## Interpretation and limitations

V1 materially reduces false passes from 1.0000 to 0.6250 on this benchmark but
does not address semantic support. Its false-block rate is 0.0000 on the
successful predictions, while its coverage remains structurally limited.

V2 cannot be compared on quality because all 24 real provider calls failed.
The configured key and model were present, but the adapter reported only
`LLMProviderUnavailableError`; the underlying credential/network/provider
detail was deliberately not exposed. V2 must be rerun as an explicitly named
research retry after the provider issue is diagnosed, without changing the
frozen benchmark or prompt.

## Attempt 2 diagnosis

Attempt 1 remains preserved in `artifacts/experiments/EX-003/ex003_run.json`.
A separate synthetic provider smoke test using the existing
`MistralLLMProvider` also failed with `LLMProviderUnavailableError` in
102.56 ms. Configuration presence checks were positive:

- `MISTRAL_API_KEY` configured: YES;
- `MISTRAL_MODEL` configured: YES;
- installed `mistralai`: 2.7.1.

The safe network check to `api.mistral.ai:443` failed, so the current root
cause is classified as **D — network/DNS/TLS/proxy connectivity failure**.
This is a precondition failure outside the EX-003 verifier logic. No
structured V2 benchmark retry was run, and no V2 code or prompt was changed.

Corrective action before a retry: restore outbound TCP/TLS access to
`api.mistral.ai:443` or configure the approved corporate proxy/firewall path,
then repeat one synthetic `Réponds uniquement par le mot OK.` smoke test. Do
not rerun the frozen 24-case V2 set until that smoke test succeeds.

## Structured V2 diagnosis and technical correction

The local structured smoke failure was traced to **G1 — response format not
sent / wrong mode**. `LLMGenerationRequest` had no response-format field and
`MistralLLMProvider` called `chat.complete_async` without one. The SDK therefore
used its default plain-text response mode. The local V2 parser then attempted
to parse the returned text as `VerificationOutput`; the smoke wrapper reported
the bounded-schema failure. The raw local model body was not included in the
reported output, so no raw body or secret-bearing metadata is recorded here.

The smallest technical correction was applied:

- add an optional provider-neutral `response_format` request field;
- pass it through the Mistral adapter;
- build the existing `VerificationOutput` Pydantic JSON schema with the
  installed Mistral SDK and send it as `json_schema` for V2;
- add a unit assertion that the V2 request transmits the `VerificationOutput`
  schema.

Changed technical files: `app/modules/ai/llm.py`,
`app/modules/ai/providers/mistral.py`, and the research V2 prompt/test files.
Semantic prompt, verdict policy, benchmark, human labels, and frozen case set
were not changed. No live post-fix smoke or Attempt 2 was run from the Codex
environment; local Windows must rerun the two smoke commands before Attempt 2.

V3 remains gated and was not evaluated. No production verifier or citation
resolver is selected by this result, and no RD-004 is created.

## Reproduction

```powershell
python -m experiments.verification.ex003_response_verification.run_ex003
```

Raw run output and metrics are under the ignored research artifact path:

- `artifacts/experiments/EX-003/ex003_run.json`
- `artifacts/experiments/EX-003/ex003_metrics.json`

## Attempt 2 — completed structured V2 retry

Attempt 2 used the same frozen 24-case set, benchmark labels, evidence
payloads, V2 prompt, and provider configuration. It used a separate artifact
stem (`ex003_v2_attempt2`) and therefore preserved Attempt 1. The provider
returned valid bounded `VerificationOutput` objects for all 24 cases.

| Metric | V0 | V1 | V2 Attempt 2 |
|---|---:|---:|---:|
| Successful predictions | 24 | 24 | 24 |
| Failed predictions | 0 | 0 | 0 |
| Unsupported/contradicted claim rate | 0.4118 | 0.4167 | 0.2000 |
| Public-source attribution correctness | 0.7500 | 0.7500 | 0.7500 |
| Citation/evidence coverage | 0.0000 | 0.0000 | 0.9231 |
| False-pass rate | 1.0000 | 0.6250 | 0.4375 |
| False-block rate | 0.0000 | 0.0000 | 0.0000 |

V2 confusion matrix:

```text
expected pass               -> pass: 5
expected pass_with_warnings -> pass: 2, pass_with_warnings: 1
expected block              -> pass: 1, pass_with_warnings: 6, block: 9
```

### Case-level verdict analysis

For this benchmark, `pass` and `pass_with_warnings` are both false passes
when the expected verdict is `block`.

V0 has false passes on all expected-block cases:
VER-009, VER-011, VER-013, VER-014, VER-015, VER-016, VER-017, VER-018,
VER-019, VER-022, VER-023, VER-025, VER-026, VER-027, VER-028, VER-029.
It has no false blocks.

V1 correctly blocks VER-016, VER-017, VER-018, VER-019, VER-028, and VER-029.
Its false passes are VER-009, VER-011, VER-013, VER-014, VER-015, VER-022,
VER-023, VER-025, VER-026, and VER-027. It has no false blocks. Its
false-block cases are VER-006, VER-021, and VER-024 because the deterministic
variant returns `pass` for expected `pass_with_warnings`; these are verdict
label mismatches, not `block` predictions, and therefore are not counted by
the registered false-block metric.

V2 correctly blocks VER-009, VER-011, VER-013, VER-014, VER-015, VER-016,
VER-025, VER-026, and VER-027. Its false passes are VER-017, VER-018, VER-019,
VER-022, VER-023, VER-028, and VER-029. It has no false blocks under the
registered metric. As with V1, VER-021 and VER-024 are predicted `pass` while
the human label is `pass_with_warnings`.

### Complementarity on expected-block cases

- Correctly blocked by both: VER-016.
- Correctly blocked only by V1: VER-017, VER-018, VER-019, VER-028, VER-029.
- Correctly blocked only by V2: VER-009, VER-011, VER-013, VER-014, VER-015,
  VER-025, VER-026, VER-027.
- Missed by both: VER-022, VER-023.
- Non-block cases incorrectly blocked by either variant: none.

The complementarity gate is therefore **V3 experimentally justified: YES**.
V1 contributes five correct detections absent from V2, and V2 contributes
eight correct detections absent from V1. This is evidence of complementary
structural and semantic behavior, not merely an architectural assumption.

### Defect-type analysis

Using only frozen benchmark metadata and human annotations:

- Structural source attribution / citation defects: VER-016, VER-017,
  VER-018, VER-019.
- Semantic unsupported or contradicted claims: VER-009, VER-011, VER-013,
  VER-014, VER-015, VER-022, VER-023, VER-025, VER-026, VER-027.
- Mixed structural plus semantic defects: VER-028, VER-029.

V1 is effective on the structural citation group and does not evaluate
semantic support. V2 identifies more semantic defects, but still misses the
unresolved-citation cases VER-017 and VER-019 and some mixed cases. The two
variants consequently have measured, non-overlapping strengths.

### Metric semantics audit

- `false_pass_rate`: numerator is expected-block rows predicted `pass` or
  `pass_with_warnings`; denominator is all expected-block rows (16). It is a
  verdict prediction metric and is directly comparable across V0/V1/V2.
- `false_block_rate`: numerator is non-block rows predicted `block`; denominator
  is all non-block rows (8). It is a verdict prediction metric and is directly
  comparable across variants. The implementation does not count `pass` versus
  `pass_with_warnings` disagreements as false blocks.
- `unsupported_claim_rate`: numerator is human claims labelled unsupported or
  contradicted among rows the variant allowed; denominator is all material
  claims in those allowed rows. It is conditional on the variant's decisions,
  so it is informative but not a standalone verifier-quality score and is
  only meaningfully compared with that denominator limitation.
- `public_source_attribution_correctness`: numerator is the number of frozen
  rows with `expected_public_source_correct=true`; denominator is all 24 rows.
  It does not inspect predictions, so the identical 0.7500 across variants is
  expected and is a benchmark/data characteristic, not a verifier-quality
  result. This is a metric-design limitation, not an implementation bug.
- `citation_evidence_coverage`: numerator is material claims for which the
  output cites at least one expected evidence ID; denominator is all material
  claims with non-empty expected evidence IDs. It measures claim-level
  evidence selection, not verdict accuracy. V0 and V1 return no claim-level
  evidence predictions by design, hence 0.0; V2 returned them and achieved
  0.9231.

### Verdict macro-F1

Macro-F1 uses the three registered classes (`pass`, `pass_with_warnings`,
`block`). When a class has no predicted samples, precision is defined as 0 and
its F1 is 0.

| Variant | Class | Precision | Recall | F1 |
|---|---|---:|---:|---:|
| V0 | pass | 0.2083 | 1.0000 | 0.3448 |
| V0 | pass_with_warnings | 0.0000 | 0.0000 | 0.0000 |
| V0 | block | 0.0000 | 0.0000 | 0.0000 |
| V0 | **macro-F1** |  |  | **0.1149** |
| V1 | pass | 0.2778 | 1.0000 | 0.4348 |
| V1 | pass_with_warnings | 0.0000 | 0.0000 | 0.0000 |
| V1 | block | 1.0000 | 0.3750 | 0.5455 |
| V1 | **macro-F1** |  |  | **0.3267** |
| V2 | pass | 0.6250 | 1.0000 | 0.7692 |
| V2 | pass_with_warnings | 0.1429 | 0.3333 | 0.2000 |
| V2 | block | 1.0000 | 0.5625 | 0.7200 |
| V2 | **macro-F1** |  |  | **0.5631** |

### V2 operational cost and latency

Attempt 2 used 35,203 prompt tokens, 5,222 completion tokens, and 40,425
total tokens across 24 cases. Averages were 1,466.79 prompt tokens, 217.58
completion tokens, and 1,684.38 total tokens per case. V2 latency was
1,926.5329 ms median and 3,030.6243 ms p95. Monetary cost remains **not
reliably attributed** because no reproducible pricing mechanism is part of
this experiment.

### V3 and RD-004 gates

V3 is experimentally justified by the observed complementarity above. No V3
was run, and no post-hoc threshold or hypothesis was introduced. A future
V3 hypothesis must be frozen before execution; it should test whether the
composition of deterministic structural checks and model-assisted semantic
verification reduces the V2 false-pass rate below 0.4375 while preserving the
registered false-block rate at 0, or quantify the trade-off if that is not
achieved.

RD-004 is **not ready**: the required V3 experiment has not been executed.
No production verifier, citation resolver, or RD-004 decision is selected by
this result.

### Attempt 2 artifacts

- `artifacts/experiments/EX-003/ex003_v2_attempt2.json`
- `artifacts/experiments/EX-003/ex003_v2_attempt2_metrics.json`

The benchmark and human labels were not modified. V3, production
verification, and RD-004 remain explicitly deferred.

## V3 Follow-up Experiment

### Design and hypothesis

V3 was justified by the measured complementarity above. The cascade rule was
frozen before metric calculation:

```text
if V1 == block:
    V3 = block
else:
    V3 = V2
```

Primary hypothesis H1:

> On the same frozen 24-case benchmark, V3 will reduce the false-pass rate
> below 0.4375 while not increasing the false-block rate above 0.0000.

The secondary operational hypothesis was that V1 terminations would avoid
some model-assisted calls. V3 was proposed after observing V1/V2
complementarity on this same benchmark; this post-hoc design limits the
strength of generalization.

### Replay method

V3 was a deterministic replay of the already recorded per-case V1/V2
predictions in `ex003_v2_attempt2.json`. No Mistral or Qdrant call was made.
Prediction construction consumed only recorded case IDs, verdicts, reasons,
timings, and usage. Human expected labels were read only afterward by the
metric evaluator. The benchmark and V0/V1/V2 artifacts were not overwritten.

### V3 results

- Frozen cases: 24
- Mistral calls during V3: 0
- False-pass rate: **0.1250**
- False-block rate: **0.0000**
- Correctly blocked: VER-009, VER-011, VER-013, VER-014, VER-015, VER-016,
  VER-017, VER-018, VER-019, VER-025, VER-026, VER-027, VER-028, VER-029
- False passes: VER-022, VER-023
- False blocks: none
- Correctly allowed under the registered non-block safety metric: VER-004,
  VER-005, VER-006, VER-007, VER-008, VER-012, VER-021, VER-024

Confusion matrix:

```text
expected pass               -> pass: 5
expected pass_with_warnings -> pass: 2, pass_with_warnings: 1
expected block              -> pass_with_warnings: 2, block: 14
```

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| pass | 0.7143 | 1.0000 | 0.8333 |
| pass_with_warnings | 0.3333 | 0.3333 | 0.3333 |
| block | 1.0000 | 0.8750 | 0.9333 |
| **Macro-F1** |  |  | **0.7000** |

V3 correctly blocks 14 cases, versus 6 for V1 and 9 for V2. This matches
the observed complementarity: V3 retains V1's five unique correct blocks and
V2's eight unique correct blocks, plus the shared case.

### Operational cascade effect

- V1 evaluated: 24 cases
- V1 block terminations: 6 cases
- V2 calls required: 18
- V2 calls avoided: 6
- Benchmark-specific call reduction: 6/24 = **25.0%**

This percentage is specific to this frozen benchmark and is not a production
savings claim.

Replayed cascade latency, calculated as V1 latency for terminated cases and
V1 plus V2 latency otherwise:

- Median: **1789.0351 ms**
- p95: **3030.6350 ms**

Token usage:

- V2 baseline: 40,425 total tokens
- V3 replay: 30,955 total tokens
- Reduction: 9,470 tokens (**23.4261%**)
- V3 averages per benchmark case: 1129.96 prompt, 159.83 completion,
  1289.79 total tokens
- Monetary cost: not reliably attributed

### Metric limitations

`unsupported_claim_rate` and `citation_evidence_coverage` are **NOT
COMPARABLE** for V3: cases blocked by V1 do not have V2 claim-level outputs,
so assigning V1 structural outcomes to semantic metrics would be invalid.
The fixed `public_source_attribution_correctness = 0.75` remains a benchmark
data characteristic and is not useful for selecting V3.

VER-030 remains excluded from primary metrics and was not regenerated.

### RD-004 gate

RD-004 is **READY: YES**, subject to the explicitly retained post-hoc
limitation and human architecture review. V3 improves the measured false-pass
rate from 0.4375 to 0.1250, preserves the observed false-block rate at 0, and
documents reduced model calls and token usage. This does not itself implement
or select a production verifier.

Future validation on an expanded or independent benchmark is required to
strengthen the conclusion because V3 was proposed after observing V1/V2
results on this same 24-case set.

### V3 artifacts

- `artifacts/experiments/EX-003/ex003_v3_replay.json`
- `artifacts/experiments/EX-003/ex003_v3_metrics.json`
