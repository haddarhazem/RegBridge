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
then, only if the initial coverage is partial or insufficient,
`RETRIEVING_MISSING_DOMAIN_EVIDENCE` and `REASSESSING_EVIDENCE`, followed by
`GENERATING`, `VERIFYING`, then `COMPLETED`; a stage can instead be `FAILED` or
`CANCELLED`. The browser polls approximately every 900 ms and stops on a
terminal status. It does not use timers to fabricate progress.

`RequiredDomainResolver` first records a safe, typed domain decision:
`QUESTION_EXPLICIT`, `PROJECT_CONTEXT_BROAD_QUESTION`, or `UNRESOLVED`.
Explicit question signals take priority; only a broad regulatory project
question derives domains from confirmed authorized context. `UNRESOLVED` asks
for clarification and does not start normal retrieval or Gemini generation.
There is intentionally no `GENERAL_BUSINESS` fallback for an unrecognized term:
for example, `RGBD` is never silently corrected to `RGPD`.

`EvidenceSufficiencyEvaluator` is deterministic application logic, not an LLM
or a confidence score. It assesses the already resolved required-domain set
against retrieved evidence. It classifies source coverage as:

- `SUFFICIENT`: every required domain has useful evidence.
- `PARTIAL`: at least one required domain is covered and at least one is missing.
- `INSUFFICIENT`: no useful required-domain evidence exists or retrieval is empty.

Useful evidence requires an explicit domain/topic match plus substantive
regulatory content. Raw Qdrant score alone never determines the result.
`PARTIAL` answers are instructed to remain limited to the retrieved support;
`INSUFFICIENT` skips Gemini generation and returns a safe French coverage notice.
This signal is a coverage heuristic, not legal certainty or a confidence value.

When the first assessment is `PARTIAL` or `INSUFFICIENT`, the deterministic
`MissingDomainQueryBuilder` issues at most one additional retrieval query for
each *missing* resolver domain. It reuses the existing BGE-M3/Qdrant retriever,
configured top-k and frozen collection. Queries use fixed domain vocabulary and
at most small generic terms that are confirmed in authorized context; neither a
full project description nor private documents are included. Initial and
fallback evidence are merged by stable `point_id`, deduplicated before the
generation prompt, then passed back to the same evaluator. A successful
fallback may truthfully remain `PARTIAL`; it never forces `SUFFICIENT`.

Fallback traces record only allowlisted counts, domain names, statuses and
failure codes. An initial retrieval failure remains `QDRANT_UNAVAILABLE`; a
complete supplementary-retrieval failure is `FALLBACK_RETRIEVAL_FAILED`.
Partial supplementary failures retain successfully retrieved evidence and list
only the affected domain names. Queries, project text, chunks, credentials,
headers and raw provider payloads are not persisted.

Developer diagnostics are exposed only in development (or when
`COPILOT_DIAGNOSTICS_ENABLED=true`) and show the request ID, stage summary,
initial/final coverage, fallback domain names and counts, provider/model,
verification result and safe error code. They never include prompts, queries,
chunks, private project content, JWTs, API keys or provider response bodies.

LangGraph was not introduced. External regulatory fallback/web retrieval is not
implemented here.
