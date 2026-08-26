# RD-019 — Evidence-constrained research extraction

## Decision

**No production extraction candidate selected.** The initial EX-024 diagnostic and corrected EX-024-R1 both failed the safety and utility gates.

## Evidence

EX-024 used the frozen `research-extraction-ex024-v1` benchmark: 15 controlled synthetic excerpts and 105 annotated field instances. The final live run used `mistral-small-latest` with the common frozen configuration. Results are recorded in `docs/engineering-research/results/EX-024-results.md` and the machine-readable artifact `artifacts/experiments/ex024_research_extraction_results.json`.

V1 produced 7 critical unsupported claims; V2 produced 14 and had 0/84 valid provenance coverage. V0 had 0/15 structured-valid outputs, and V3 had no accepted generated claims after bounded provider/verification failures. The production gate requires zero critical unsupported claims and usable output; no candidate meets both conditions.

EX-024-R1 corrected the confirmed evidence-contract and accounting defects without changing the benchmark or semantic prompts. The final R1 run measured V1 at 47/90 recall with 21 critical unsupported claims, V2 at 38/90 recall with 13 critical unsupported claims and 23/56 evidence entailment precision, and V3 at 23/90 recall with 8 critical unsupported claims and 16/64 UNVERIFIABLE verifier decisions. V0 remained 0/15 parseable. Therefore no R1 candidate meets the zero-critical-unsupported gate, recall floor, and applicable reliability floors.

EX-024-R2 used a fresh 12-excerpt holdout and tested the H-024-R2 extractive strategy V4. V0–V3 remained frozen comparators. V4 returned provider-unavailable for all 12 live calls, so its exact-copy hypothesis was validated only by deterministic stub tests, not by the live holdout. The R2 holdout also retained field imbalance in domains, research problem, methodology, main results and limitations; this limits interpretation of absence accuracy. R2 therefore selects NONE and does not activate production.

EX-024-R3 was the final planned balanced comparison. The 16-excerpt/128-annotation holdout achieved 8 supported and 8 absent per field. The V4 smoke passed, but the full V4 stage received HTTP 429 rate-limit failures after the comparator calls. V1–V3 again failed safety/utility gates. R3 also exposed that gold evidence locator objects were not materialized in the JSON benchmark, which is a protocol deviation.

EX-024-R3C completed V4 only after one successful health check. The separate immutable evidence manifest materialized 64/64 deterministic locators without changing statuses, canonical values, or critical labels. The R3 application contradiction was classified as an APPLICATION_METRIC/report-rendering defect, and case-level presence confusion was recomputed from frozen gold and normalized rows. V4 achieved 16/16 provider, structured, and usable cases; corrected global field evidence was TP=63, TN=64, FP=4, FN=1, with 63/67 precision and 63/64 recall, zero invalid or wrong-version evidence, exact-copy integrity 1/1, and deterministic abstract provenance 32/32. The four false positives are wrong-field exact source selections and are non-critical under the frozen gate. The V4 reliability and safety/utility gates pass, so R3C selects `extractive_evidence_locked` for the next production implementation step. No production code or persistence was activated by the research run.

## Consequence

SCRUM-209 has a research selection: only `extractive_evidence_locked` may proceed to a separately reviewed production implementation. Do not wire V0, V1, V2, or V3 into user-facing production. SCRUM-210 is not implemented.

## Limitations

The benchmark is controlled synthetic rather than a broad scientific corpus. The provider model is a moving alias. The run exposed that model-supplied evidence locators are not reliable enough without deterministic resolver enforcement. More research is required before production selection; this record intentionally does not claim that V3 wins or that V2 is production-ready.

Evidence strength: **MODERATE for rejecting the tested configurations; LOW for generalizing beyond this benchmark.**
