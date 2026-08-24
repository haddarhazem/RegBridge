# RD-018 — Investor Opportunity Brief factuality verification

Status: selected for SCRUM-205.

Use deterministic-first V2 rules over the exact persisted SCRUM-204 evidence bundle,
investor thesis snapshot, startup snapshot, confirmed facts, and canonical
SCRUM-203 matching result. Persist every claim verdict and evidence reference
in an immutable verification run. A verification run is `VERIFIED` only when
all extracted claims are `SUPPORTED`; otherwise it is `VERIFICATION_FAILED`.

The EX-023 frozen benchmark measured 100% unsupported-claim recall, 100%
precision, and 0% false-pass rate for V0. V1 made 24 live calls and returned
16 valid structured verdicts; V2 resolved 23 cases deterministically and used
one semantic fallback. Both had zero critical false passes. V2 retained the
same quality while reducing provider calls by 23 and tokens substantially.
V1's end-to-end structured-verdict reliability was 66.67% (16/24), with
invalid outputs rejected rather than interpreted as verdicts.

The original blocked attempt was caused by sandbox network permission denial,
not credentials, model, SDK, or schema. A network-enabled smoke and benchmark
then succeeded.

The supplementary EX-023-S1 holdout contained five fresh supported paraphrases
and five unsupported/adversarial claims. In the latest persisted run, V1
accepted 4/5 supported paraphrases and had 3/10 invalid structured outputs.
V2 used five semantic fallback calls, accepted 5/5 supported paraphrases,
rejected all five adversarial cases, and had zero critical false passes or
false blocks. It avoided five provider calls relative to V1. This confirms a
useful but bounded V2 improvement; evidence remains MODERATE because the
holdout is small and the result is model/run dependent.

The previous S1 report's V1 5/5, V2 4/5, and 20% V2 false-block figures were
corrected to match the latest persisted case rows. The persisted V2 overall
latency field (208.5 ms) was also identified as a 15-sample rather than
10-case average; the corrected intended per-case average is approximately
312.7 ms. No benchmark, label, prompt, schema, verifier logic, or provider
call was changed for this audit.

V2 is selected for SCRUM-205 production verification. It invokes the semantic
provider only for genuinely unresolved deterministic claims. Provider failure
is fail-closed and cannot mark a brief verified. V0 remains the deterministic
authority for all conclusive claims.

Verification never modifies source snapshots, matching results, or facts. It
does not approve or share a brief; those workflows remain SCRUM-206 and
SCRUM-207.
