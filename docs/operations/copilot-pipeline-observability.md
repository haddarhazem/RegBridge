# Copilot evidence sufficiency and pipeline observability

Each authenticated Copilot turn is correlated by the browser-generated
`X-Request-ID`. The same value is sent on the turn POST and on polling requests
to `GET /conversations/{thread_id}/requests/{request_id}/status`.

The route first authorizes the conversation owner and, for project
conversations, an active project membership. A request ID is never sufficient
authorization on its own. Unknown, cross-user and revoked-membership requests
all fail closed with the same not-found response.

Operational traces reuse `agent_runs`; no additional trace table or migration
is needed. The root orchestrator keeps the existing hierarchy. `CONTEXT_BUILDING`
is its child; retrieval, evidence assessment, generation and verification are
children of the regulatory-agent run. Trace payloads contain only allowlisted
stage summaries, counts, domain names, provider/model metadata, verification
verdicts and safe failure codes.

Stages are `CONTEXT_BUILDING`, `RETRIEVING_EVIDENCE`, `ASSESSING_EVIDENCE`,
`GENERATING`, `VERIFYING`, then `COMPLETED`; a stage can instead be `FAILED` or
`CANCELLED`. The browser polls approximately every 900 ms and stops on a
terminal status. It does not use timers to fabricate progress.

`EvidenceSufficiencyEvaluator` is deterministic application logic, not an LLM
or a confidence score. It derives a small required-domain set from the question
and only confirmed authorized project context. It classifies source coverage as:

- `SUFFICIENT`: every required domain has useful evidence.
- `PARTIAL`: at least one required domain is covered and at least one is missing.
- `INSUFFICIENT`: no useful required-domain evidence exists or retrieval is empty.

Useful evidence requires an explicit domain/topic match plus substantive
regulatory content. Raw Qdrant score alone never determines the result.
`PARTIAL` answers are instructed to remain limited to the retrieved support;
`INSUFFICIENT` skips Gemini generation and returns a safe French coverage notice.
This signal is a coverage heuristic, not legal certainty or a confidence value.

Developer diagnostics are exposed only in development (or when
`COPILOT_DIAGNOSTICS_ENABLED=true`) and show the request ID, stage summary,
domain coverage, chunk count, provider/model, verification result and safe error
code. They never include prompts, chunks, private project content, JWTs, API
keys or provider response bodies.

LangGraph was not introduced. External regulatory fallback/web retrieval is not
implemented here.
