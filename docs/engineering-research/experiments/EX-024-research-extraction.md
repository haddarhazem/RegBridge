# EX-024 — Evidence-constrained research extraction benchmark

## Protocol

Run V0, V1, V2, and V3 against the same frozen `research-extraction-ex024-v1` benchmark. Use the configured Mistral provider, one fixed model/configuration, temperature 0, bounded output tokens, and the same exact source text for every candidate.

V0 uses a loose machine-readable envelope without a native JSON schema or evidence requirement. V1 uses strict `SUPPORTED`/`NOT_AVAILABLE` fields. V2 adds mandatory evidence references. V3 adds a separate structured verifier that receives only one claim and its resolved evidence and cannot create or edit claims.

The benchmark has 15 synthetic source excerpts and 105 field annotations. Every supported value has a deterministic paragraph-0 locator; absent values remain explicit `NOT_AVAILABLE` gold labels. The benchmark is frozen before any provider call.

## Pre-registered metrics

Evidence precision, unsupported claim rate, extraction recall, provenance coverage, structured validity, explicit-application accuracy, critical unsupported count, numeric mutation rate, negation error rate, provider success, latency, input/output tokens, and cost where provider metadata supplies it. Every percentage is reported with denominators.

Critical unsupported claims cover technologies, results/performance, applications, TRL, IP/patent, and commercialization. The production gate is zero critical unsupported claims.

## Error analysis

The result must retain representative examples of invented applications/technologies, numeric mutations, causal or scope overclaims, negation failures, missed supported claims, invalid schemas/evidence, verifier false rejection, and provider failures. No LLM is used as the relevance judge; gold annotations are deterministic and frozen.

## Privacy and boundary

The benchmark contains controlled synthetic excerpts only. Production source bytes remain private and are resolved only through the authorized SCRUM-208 exact-version path. Experiment code is not imported by production code. SCRUM-209 produces only a private generated draft; publication, matching, and author approval remain SCRUM-210 concerns.
