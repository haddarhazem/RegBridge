# EX-022 — Investor Opportunity Brief generation

Ticket: SCRUM-204 / RQ-022

Question: Which V1 generation strategy produces a concise investor-specific
opportunity brief while preserving confirmed facts, thesis values, and the
SCRUM-203 deterministic result?

Candidates:

- V0: deterministic template from `BriefEvidenceBundle`.
- V1: the same bundle plus Mistral native JSON_SCHEMA generation, with
  deterministic validation and fallback.

The benchmark contains 10 synthetic, versioned cases covering strong and
partial fit, missing stage/financing/highlights, technology/geography fit,
confirmed traction, UNKNOWN dimensions, and prompt-injection-like excluded
input. No production or private data is used.

Controlled variables: evidence bundle, deterministic matcher result, schema,
provider model, prompt version, validator, and final five-section structure.
SCRUM-205 factual verification is intentionally out of scope.
