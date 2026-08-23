# EX-021 results

The frozen deterministic matcher achieved 20/20 dimension-and-score agreement
on the benchmark, including the 4 holdout pairs. UNKNOWN values were preserved
as UNKNOWN and excluded from the denominator. Unsupported criterion rate was
0%; unauthorized data use was 0 in the evaluator.

## Phase 1 — Old prompt-only integration

The first live Mistral comparison used prompt-only JSON generation on the
frozen 4-core and 4-adversarial cases. Provider connectivity succeeded, but
all 8 raw explanations failed structural parsing. Raw failure rate was
**100%** (8/8), deterministic fallback rate was **100%** (8/8), and
accepted-output failure rate was **0%**. No score, dimension outcome,
snapshot/version ID, or matching method was changed.

Metric definitions are explicit: `raw_failure_rate` is rejected raw
explanations divided by live LLM explanations; `fallback_rate` is deterministic
fallbacks divided by live attempts; and `accepted_output_failure_rate` is
unsafe or invalid outputs that survive validation divided by final outputs.
The eight old integration rejections all had the same recorded reason:
invalid structured explanation due to JSON parsing failure
(`Expecting value: line 1 column 1`). Missing caveat, contradiction,
unsupported criterion, UNKNOWN misuse, financial-claim, and prompt-injection
counters were all zero.

## Phase 2 — Current native JSON_SCHEMA integration

The corrected integration was validated on one M01 development smoke case and
then on the frozen 4-core and 4-adversarial holdout. All 8 current calls
reached Mistral successfully, produced schema-valid JSON, passed the existing
semantic validator, and were accepted. API success, schema-valid, semantic
pass, and accepted explanation rates were each **100%** (8/8). Fallback rate
and accepted-output failure rate were both **0%**. Score, dimension outcomes,
snapshot/version IDs, and matching method remained deterministic and unchanged.
Input tokens were 1,630, output tokens were 1,241, average latency was
approximately 1,477 ms, and estimated cost was unavailable.

The deterministic evaluator rejects changed scores, changed dimension states,
invented criteria, private-field influence, financial claims, and prompt
injection. Provider failure is specified to retain the deterministic result
with `deterministic_fallback` and no fake prose.

## Research gate

The evidence continues to support deterministic `structured_v1` matching as
the authoritative production strategy. Native JSON_SCHEMA materially improved
structured-output reliability in the current explanation component, while the
semantic validator and deterministic fallback remain mandatory. This evidence
does not change matching accuracy or make the LLM authoritative. The
production matching path now uses the validated explanation layer optionally:
deterministic matching remains authoritative, accepted explanations are
persisted as `llm`, and provider/schema/semantic failures persist the
deterministic fallback.
