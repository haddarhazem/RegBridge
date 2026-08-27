# EX-027 — Prompt-injection defense-in-depth

Related Jira: SCRUM-213. Related question: RQ-027.

The frozen synthetic benchmark is `benchmarks/prompt_injection_ex027_v1.json`
(48 cases: 32 DEV and 16 HOLDOUT), SHA-256
`fa3a42b78a06d9bbe9eca623ca5c438c42bb37f8c120836a6c082d07b3fe791e`.

P0 is the current provider prompt and deterministic backend authorization. P1
adds explicit trusted-application-policy and untrusted-data delimiters. Both
use the same configured Mistral model, temperature, tools, case order, and
benchmark. P2 is evaluated only if DEV evidence justifies quarantine; this
run did not justify it.

The opt-in runner (`EX027_LIVE=1`) stores aggregate classifications and
bounded provider metadata only under the ignored `artifacts/experiments/`
directory. It does not persist raw prompts or completions, and all benchmark
data is synthetic.
