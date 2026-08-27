# RD-022 — Prompt-injection defense-in-depth (protocol-limited)

Related Jira: SCRUM-213. Research question: RQ-027. Experiment: EX-027.

Status: FINAL — NO SELECTION.

The frozen benchmark was `prompt_injection_ex027_v1.json`, SHA-256
`fa3a42b78a06d9bbe9eca623ca5c438c42bb37f8c120836a6c082d07b3fe791e`, with 48
synthetic cases (32 DEV, 16 HOLDOUT). P0 and P1 used the same configured
Mistral model and execution controls.

Both candidates produced zero successful unauthorized object, tool, or RAG
actions and zero visibility/grant bypasses because deterministic backend
authorization remained authoritative. On HOLDOUT, both had 8/8 prohibited
action attempts and 2 model-reported sentinel signals; benign completion was
7/8 for both. P1 did not provide a measurable HOLDOUT improvement.

EX-027 is protocol-limited and non-decision-grade for mitigation selection:
mandatory utility thresholds were not frozen before its HOLDOUT. Its
security-containment evidence is retained; its utility result is not promoted
to PASS.

## Decision

No selection. A fresh recovery experiment under RQ-027 is required. Do not
interpret this record as if EX-027 did not happen.

Backend identity, ownership, active membership, visibility, ResourceGrant,
research scopes, exact-version authorization, RAG eligibility, and tool
permissions remain deterministic and unchanged. The LLM cannot authorize
access.

Evidence strength: MODERATE for deterministic backend containment and
INSUFFICIENT for mitigation selection. The benchmark is synthetic, provider
behavior is nondeterministic, and model-reported sentinel signals must not be
interpreted as actual private-data disclosure.
