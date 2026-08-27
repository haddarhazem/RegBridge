# EX-027 results — Prompt-injection defense-in-depth

Benchmark: `prompt_injection_ex027_v1.json`; SHA-256
`fa3a42b78a06d9bbe9eca623ca5c438c42bb37f8c120836a6c082d07b3fe791e`.

The live comparison ran 48 synthetic cases per candidate (32 DEV, 16
HOLDOUT). Raw aggregate output is in the ignored
`artifacts/experiments/ex027-results.json`.

| Metric | P0 | P1 |
| --- | ---: | ---: |
| Raw valid / 48 | 42 | 48 |
| Raw failure rate | 12.5% | 0% |
| Model attempts, DEV | 26/32 | 32/32 |
| Model attempts, HOLDOUT | 8/8 | 8/8 |
| Model-reported sentinel signals, DEV | 12 | 15 |
| Model-reported sentinel signals, HOLDOUT | 2 | 2 |
| Successful unauthorized object/tool/RAG actions | 0 | 0 |
| Visibility bypasses | 0 | 0 |
| Grant/scope bypasses | 0 | 0 |
| Benign completion, HOLDOUT | 7/8 (87.5%) | 7/8 (87.5%) |
| Average provider latency | 8207.695 ms | 1281.041 ms |

The sentinel metric is a structured model-output signal, not an actual
private-data disclosure: no real private data or protected backend resource
was supplied, and no unauthorized backend action was executed.

## Decision

P0 is selected. P1 did not improve HOLDOUT prohibited-action attempts,
sentinel signals, or benign completion, and P2 was not justified. Production
retains deterministic backend authorization, exact grants/versions, safe RAG
eligibility, and existing untrusted-content instructions. The LLM never
authorizes access.

Evidence strength: MODERATE. The benchmark is synthetic and small, and the
provider is nondeterministic; results do not establish universal robustness.
