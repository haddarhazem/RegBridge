# RD-016 — Structured investor-startup matching baseline

Status: selected for SCRUM-203.

Select the deterministic `structured_v1` matcher for the current production
baseline. It evaluates only sector, stage, geography, technology and ticket
when both sides contain comparable structured data. MATCH is one point,
MISMATCH is zero, and UNKNOWN is excluded. With no comparable dimensions, the
score is null.

The report persists exact investor thesis version provenance and an immutable
authorized startup snapshot. It is a compatibility report, not investment
advice or a success/return prediction.

The initial prompt-only holdout produced 0/8 acceptable explanations and
remains historical evidence. The corrected native JSON_SCHEMA integration
produced 8/8 schema-valid and semantically accepted explanations on the final
holdout, with 0 unsafe accepted outputs. This materially improves explanation
format reliability, but does not alter the decision that deterministic matching
is authoritative. Any LLM explanation path remains explanation-only and must
retain semantic validation and deterministic fallback.
