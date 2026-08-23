# EX-021 results

The frozen deterministic matcher achieved 20/20 dimension-and-score agreement
on the benchmark, including the 4 holdout pairs. UNKNOWN values were preserved
as UNKNOWN and excluded from the denominator. Unsupported criterion rate was
0%; unauthorized data use was 0 in the evaluator.

The live Mistral V1 holdout was executed against the frozen 4-core and
4-adversarial cases. Provider connectivity succeeded, but all 8 raw
explanations failed the required structured `structured_v1` JSON parsing gate.
Accordingly: raw Mistral failure rate was **100%** (8/8), deterministic
fallback rate was **100%** (8/8), and accepted-output failure rate was **0%**.
No score, dimension outcome, snapshot/version ID, or matching method was
changed by the provider path. Input tokens were 1,726, output tokens were
2,068, average latency was approximately 1,603 ms, and estimated cost was
unavailable.

The deterministic evaluator rejects changed scores, changed dimension states,
invented criteria, private-field influence, financial claims, and prompt
injection. Provider failure is specified to retain the deterministic result
with `deterministic_fallback` and no fake prose.

## Research gate

The evidence supports production of V0 as the safe current baseline. V1 LLM
explanations are rejected for production because every raw explanation failed
the acceptance gate. The deterministic validator and fallback preserved a
zero accepted-output failure rate, so the reduced deterministic output remains
safe when the provider degrades fidelity.
