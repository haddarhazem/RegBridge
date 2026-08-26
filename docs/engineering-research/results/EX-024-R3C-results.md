# EX-024-R3C — V4 completion

## R3 preservation

R3 was not overwritten. R3C is the immutable V4-only continuation run
`20260826T111253Z`, using the same frozen 16-case benchmark and the separate
evidence-locator amendment. V0–V3 were read from the original R3 artifact and
were not rerun.

## Metric audit

The application contradiction was an `APPLICATION_METRIC`/report-rendering
defect: presence accuracy had been presented as TP/TN/FP/FN. Canonical
case-level presence confusion was recomputed from each candidate's normalized
predictions and frozen gold. V2 is `TP=8 TN=8 FP=0 FN=0` and V3 is
`TP=3 TN=8 FP=0 FN=5` for this R3 dataset. The report/scorer audit is now
explicit and uses one case-level calculation; gold values and labels are
unchanged.

The corrected R3C V4 result is `TP=63 TN=64 FP=4 FN=1`, precision `63/67`,
recall `63/64`, specificity `64/68`, and balanced accuracy `0.9628`. There
were 67 exact source-derived selected values, 63 exact gold matches, four
wrong-field extra selections, and one missed supported item. The four extras are not
generated factual paraphrases: they are exact copied source segments.

| Field | TP | TN | FP | FN | Precision | Recall | Specificity | Balanced |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| domains | 8 | 8 | 0 | 0 | 8/8 | 8/8 | 8/8 | 1.0000 |
| technologies | 8 | 8 | 0 | 0 | 8/8 | 8/8 | 8/8 | 1.0000 |
| research_problem | 8 | 8 | 0 | 0 | 8/8 | 8/8 | 8/8 | 1.0000 |
| methodology | 8 | 8 | 4 | 0 | 8/12 | 8/8 | 8/12 | 0.8333 |
| main_results | 8 | 8 | 0 | 0 | 8/8 | 8/8 | 8/8 | 1.0000 |
| explicit_applications | 8 | 8 | 0 | 0 | 8/8 | 8/8 | 8/8 | 1.0000 |
| keywords | 7 | 8 | 0 | 1 | 7/7 | 7/8 | 8/8 | 0.9375 |
| limitations | 8 | 8 | 0 | 0 | 8/8 | 8/8 | 8/8 | 1.0000 |

Claim precision is `63/67`; unsupported exact selections are `4/67`; critical
unsupported claims, numeric mutations, negation mutations, invalid evidence,
and wrong-version evidence are all zero. Provider, structured, and usable
rates are each `16/16`. Average latency was 1,597.8 ms; input tokens were
4,551 and output tokens 2,926. Estimated cost was unavailable from provider
metadata.

## Gold evidence amendment

The immutable manifest contains 64/64 supported locators. All resolve to
non-empty text from the correct source version and source hash. Original gold
hash: `7844F7AD2A2FC5A9883FAD873C7252B60B1E61B18E1EE09760F4E70F60220A17`.
Manifest hash: `5B71D34FFCB996AB33A6F6CB491BDD6D4FF07C19316D178A621B66B1FF66B985`.
Statuses, canonical values, and critical labels were not changed.

## V4 gates

The provider reliability gate passed at 16/16 (required 15/16). Exact-copy
integrity is 1/1. The deterministic abstract emits only clauses assembled from
accepted source text; its factual provenance is 32/32, unsupported abstract
claims are 0, numeric mutations are 0, and invented applications are 0.
Application presence is `TP=8 TN=8 FP=0 FN=0`, precision 1.0000, recall 1.0000.
All mandatory safety and utility gates pass.

## Decision

V4 passes the frozen R3C gates and is the selected strategy:
`extractive_evidence_locked`.

No production implementation is activated in this research completion. The
production wiring remains the next controlled implementation step and must
retain exact source-ID validation, exact-copy behavior, deterministic abstract
generation, authorization, and private draft status.

## Limitations

The original initial/R1 raw artifacts were not preserved before immutable
storage was introduced. R2 had a balance deviation. R3 initially omitted
materialized locator objects; the separate manifest repairs that protocol
metadata without changing semantics. The R3 application reporting defect is
corrected in the audit. The model is a moving provider alias and the benchmark
is controlled synthetic text, so evidence is strong for this protocol and
limited for broader scientific corpora.
