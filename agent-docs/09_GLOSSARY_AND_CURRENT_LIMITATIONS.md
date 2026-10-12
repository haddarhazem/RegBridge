# Glossary and Current Limitations

## Glossary

### Active membership

A `project_members` relationship in the active state. Invited or revoked relationships do not grant project privileges.

### Agent run

One persisted AI execution identified by `agent_runs.id`. It may be a root or child run.

### AuthorizedContextBuilder

The application boundary that authorizes a caller, loads data through repositories, minimizes it, and produces a typed AI request.

### Business role

A database-controlled account role such as entrepreneur, investor, or researcher. It is not the same as a project membership role.

### Confirmed fact

A project fact whose status/provenance makes it eligible for trusted context. Pending conversational captures are not equivalent.

### Deterministic fallback

A safe response generated without trusting rejected provider output. It preserves authoritative structure and communicates gaps.

### Document version

An immutable record and private object corresponding to one exact uploaded file revision.

### Evidence sufficiency

The assessment of whether retrieved evidence covers the required domain and the requested specificity. Values include sufficient, partial, and insufficient.

### Exact snapshot

An immutable input state referenced by a derived assessment, match, brief, extraction, or analysis so the result remains reproducible.

### Official-source fallback

Optional allowlisted HTTPS retrieval from approved authoritative domains when local regulatory evidence remains inadequate. It is not generic web search.

### Project Knowledge Graph

A derived, provenance-aware read model assembled from PostgreSQL project records. It is not a Neo4j database and does not replace source tables.

### Request ID

A correlation identifier shared by root/child runs. It is not the unique primary key of an agent run.

### Resource grant

An explicit authorization for a grantee to access a specific shared resource. It does not create broad project membership.

### Trace-safe projection

A bounded allowlist-based Pydantic representation suitable for persistence/observability without secrets or unnecessary private content.

## Current limitations and cautions

### Researcher frontend

Research backend workflows are implemented, but there is not yet a complete researcher workspace equivalent to the entrepreneur and investor UIs.

### Frontend redesign in progress

V1.3 visual/layout refinements are active. Shared landing, auth, entrepreneur, and investor files may be dirty. Future agents must inspect and preserve existing work.

### Live providers are environment-dependent

Mistral, Gemini, DeepSeek, Ollama, Qdrant Cloud, and official-source network checks require explicit local configuration and, for controlled external-data tests, authorization. Ordinary tests must remain independent of those services.

### Official-source fallback defaults off

The feature is supported but intentionally disabled by default. Enabling it does not guarantee sufficient evidence; partial/insufficient outcomes remain valid.

### Semantic contract analysis is feature-gated

External document processing and contract semantic analysis require explicit settings. Without them, structural/partial results may be the correct behavior.

### No Patent Agent

Do not add or document a Patent Agent. The approved agent set includes currently implemented regulatory and contract capabilities within the accepted architecture.

### Qdrant is not authorization

Qdrant is used for regulatory evidence retrieval. It does not decide project membership, grant access, or store the authoritative project knowledge graph.

### UI output is not legal or investment advice

Regulatory assessments, roadmaps, compliance scores, matches, briefs, and contract findings are decision-support artifacts with provenance and limitations. Avoid guarantees, certification claims, predictions, or assertions of legal validity.

### Historical documents can lag code

Some feature documents were written before workers, grants, or production agents were implemented. Use the source-of-truth order from [README](README.md), and update stale documentation when a ticket changes real behavior.

## Deliberately unsupported shortcuts

- Authentication bypasses.
- Trusting token roles as application authorization.
- Authorizing from UUID knowledge.
- Storing uploaded file bodies in PostgreSQL.
- Mutable document versions.
- Running AI on quarantined/unscanned content.
- Serializing arbitrary objects into trace JSON.
- Production imports from `experiments`.
- Generic uncontrolled web search for regulatory evidence.
- Separate accounts/authentication systems per business role.
- One microservice per agent.

## How to update this guide

Update the relevant file when a ticket changes architecture, runtime commands, security boundaries, user journeys, or known limitations. Keep explanations tied to code paths and decisions. Avoid copying generated reports or temporary benchmark output into this tracked guide.

