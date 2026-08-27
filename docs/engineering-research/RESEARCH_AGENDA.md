# Research Agenda

Questions marked `PLANNED` are recorded for future work only. This document
does not authorize product implementation or a framework choice.

## RQ-001 - Orchestration architecture

Which approach gives RegBridge the best trade-off between authorization
control, traceability, testability, complexity, extensibility, and failure
handling?

Candidates: a lightweight Python/Pydantic orchestrator and one credible
orchestration framework.

Related Jira: SCRUM-183

## RQ-002 - Regulatory retrieval

Which retrieval configuration best retrieves supporting regulatory evidence?
Variables may include chunk size, overlap, top-k, dense retrieval, hybrid
retrieval, and reranking. Metrics may include Recall@k, Precision@k, MRR,
evidence coverage, latency, and cost.

Related Jira: SCRUM-184

## RQ-003 - Response verification

Does a dedicated verification stage measurably reduce unsupported claims and
citation errors?

Candidates: no verifier, deterministic checks, model-assisted verification,
and a combined strategy. Metrics include unsupported claim rate, citation
correctness, false pass rate, false block rate, latency, and cost.

Related Jira: SCRUM-185

## RQ-004 - Quality / latency / cost

Which model/configuration gives the best trade-off for a defined RegBridge
workload? Metrics include task quality, structured-output validity, groundedness,
latency, token usage, cost, and failure rate.

Related Jira: SCRUM-186

## RQ-005 - Prompt injection robustness

**PLANNED / FUTURE.** How robust is document/RAG-grounded execution against
indirect prompt injection? Potential metrics include attack success rate, task
completion rate, citation integrity, and false refusal rate. Do not implement
this legacy question; SCRUM-213 records the scoped study as RQ-027 / EX-027.

## RQ-027 - Prompt-injection defense-in-depth

Which minimal defense-in-depth strategy reduces prompt-injection following and
unauthorized tool/RAG behavior while preserving legitimate RegBridge task
completion?

Candidates: P0 current production baseline, P1 explicit trusted/untrusted
context separation, and bounded P2 quarantine only if DEV evidence justifies
it. Related experiments: EX-027 and EX-027-R1. Decisions: RD-022 and RD-023.

## Later planned questions

| Topic | Jira | Status |
| --- | --- | --- |
| Contract extraction | SCRUM-193 | PLANNED |
| Compliance scoring methodology | SCRUM-195 | PLANNED |
| Investor/startup matching | SCRUM-203 | PLANNED |
| Pitch factuality verification | SCRUM-205 | PLANNED |
| Evidence-constrained scientific extraction | SCRUM-209 | PLANNED |
| Structured vs semantic research matching | SCRUM-211 | PLANNED |
