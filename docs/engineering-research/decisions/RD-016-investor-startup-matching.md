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

V1 LLM explanation is deferred behind a provider-availability and holdout
gate. A future real-provider experiment may enable it only if deterministic
score/dimensions remain authoritative, prompt injection is contained, no
unsupported criteria or financial claims are accepted, and provider failure
falls back safely.
