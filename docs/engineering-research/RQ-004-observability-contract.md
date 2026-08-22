# RQ-004 — GenAI observability contract

## Question

Which metadata and protocol allow GenAI configurations to be compared
reproducibly on quality, latency, and usage/cost?

## Current instrumentation contract

Production and research executions should record, through the existing
SCRUM-182 trace allowlist:

- provider and logical model identifier;
- prompt version and operation/stage;
- workload or dataset version for experiments;
- duration, status, and bounded error category;
- prompt, completion, and total tokens when returned;
- monetary cost only when reproducibly configured;
- bounded source/evidence identifiers where relevant;
- request, conversation/message, and agent-run correlation identifiers.

Prompts, private documents, credentials, arbitrary provider bodies, and
chain-of-thought are not observability metadata and remain excluded.

Token usage is recorded when available. No monetary pricing mechanism is
currently configured, so estimated cost remains null rather than being
invented.

No new provider/model comparison was necessary for SCRUM-186: this ticket
establishes the instrumentation needed for future comparisons. Future
comparisons must use the same frozen workload and must not claim that one
model is globally better.
