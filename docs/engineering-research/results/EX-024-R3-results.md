# EX-024-R3 — Final technical audit and balanced comparison

## V4 forensic audit

The V4 failures were `HTTP 429` and are classified as `RATE_LIMIT`. They were not client validation, schema serialization, response parsing, authentication, network or timeout failures. V2–V3 calls consumed the provider quota before the V4 stage; the V4 smoke immediately before R3 succeeded. The V4 schema was locally serializable, accepted by the mocked Mistral adapter, contained no factual `value` property, and the live smoke returned valid IDs with exact copied text.

The smallest difference responsible for the R3 failure was provider quota state, not V4 semantics or schema. No semantic V4 change was made.

## Scoring audit

Ten-plus representative V1 outputs were reviewed. Examples included `lunar dust transport` versus the gold sentence `This research examines lunar dust transport.`, `particle-tracking simulation` versus `We use a particle-tracking simulation.`, `habitat planning` versus `The stated application is habitat planning.`, and keyword tokens versus the complete author-keyword sentence. These are deterministic `PARAPHRASE_OF_SUPPORTED` or `GRANULARITY_MISMATCH` cases under the frozen literal metric, not scorer bugs. Numeric changes and extra field selections remain real unsupported/mutation errors.

The scorer correctly counts exact supported values, unsupported values and misses. Application reporting was corrected conceptually to binary confusion matrices rather than relying on accuracy alone. R3 application counts were V0 0/8/0/8, V1 8/8/0/0, V2 8/8/0/0, V3 3/8/0/5 and V4 0/8/0/8 for TP/TN/FP/FN.

## R3 benchmark and deviations

The benchmark has 16 fresh excerpts and 128 field annotations, exactly 8 supported and 8 absent for every field. SHA-256: `7844F7AD2A2FC5A9883FAD873C7252B60B1E61B18E1EE09760F4E70F60220A17`.

The R3 JSON records exact source values and the deterministic segment policy, but does not materialize per-item `gold_evidence_locators` objects. Therefore the strict gold-locator gate is a protocol deviation. The deterministic source text is sufficient to derive the segment, but it must not be retroactively treated as an explicitly frozen locator annotation.

## R3 metrics

| Metric | V0 | V1 | V2 | V3 | V4 |
|---|---:|---:|---:|---:|---:|
| Provider success | 16/16 | 16/16 | 16/16 | 5/16 | 0/16 |
| Parse/structured validity | 0/16 | 9/16 | 16/16 | 5/16 | 0/16 |
| Usable/conclusive rate | 0/16 | 9/16 | 8/16 | 3/16 | 0/16 |
| Claim precision | 0/0 | 19/81 | 2/76 | 4/27 | 0/0 |
| Unsupported claim rate | 0/0 | 62/81 | 74/76 | 23/27 | 0/0 |
| Extraction recall | 0/64 | 19/64 | 2/64 | 4/64 | 0/64 |
| Critical unsupported claims | 0 | 19 | 23 | 8 | 0 |
| Numeric mutations | 0 | 3 | 7 | 2 | 0 |
| Negation errors | 0 | 0 | 0 | 0 | 0 |
| Provenance coverage | N/A | N/A | 2/2 | 4/4 | N/A |
| Exact-copy integrity | N/A | N/A | N/A | N/A | N/A |
| Abstract provenance | N/A | N/A | N/A | N/A | N/A |
| Average latency | 1276 ms | 1868 ms | 1775 ms | 1595 ms | 165 ms |
| Input tokens | 5079 | 4887 | 5287 | 1652 | N/A |
| Output tokens | 2560 | 3850 | 4128 | 1405 | N/A |

V4 exact-copy metrics are N/A because every live call was rate-limited. Controlled V4 tests remained exact-copy PASS.

## Decision

NONE. V0–V3 fail safety or utility gates. V4 cannot be selected because R3 live V4 execution was rate-limited and the strict gold-locator annotation gate was not satisfied. No production extraction was activated.
