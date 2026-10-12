# RegBridge Agent Guide

This directory is the practical entry point for coding agents working on RegBridge. It explains the application as it exists in the repository, the boundaries that must remain intact, and the safest place to make a change.

It supplements `AGENTS.md`; it does not replace it. Always read the repository-level instructions first.

## Read in this order

1. [System architecture](01_SYSTEM_ARCHITECTURE.md)
2. [Domain and API map](02_DOMAIN_AND_API_MAP.md)
3. [Security, authentication, and data boundaries](03_SECURITY_AUTH_AND_DATA_BOUNDARIES.md)
4. [AI, Copilot, and retrieval](04_AI_COPILOT_AND_RETRIEVAL.md)
5. [Frontend and user journeys](05_FRONTEND_AND_USER_JOURNEYS.md)
6. [Database, documents, and versioning](06_DATABASE_DOCUMENTS_AND_VERSIONING.md)
7. [Testing, operations, and troubleshooting](07_TESTING_OPERATIONS_AND_TROUBLESHOOTING.md)
8. [Change playbook](08_CHANGE_PLAYBOOK.md)
9. [Glossary and current limitations](09_GLOSSARY_AND_CURRENT_LIMITATIONS.md)

## Source-of-truth hierarchy

When sources disagree, use this order:

1. The current Jira ticket and its Research / Engineering Investigation section.
2. `AGENTS.md` and explicit security constraints.
3. The current executable code, migrations, and tests.
4. [Database schema V2.1](../docs/specs/RegBridge_DATABASE_SCHEMA_V2.1_RESEARCH.md) for approved database names and domain boundaries.
5. [Architecture/product decisions](../docs/decisions/RegBridge_Decisions_et_tracabilite_v2.0.md) and accepted ADRs.
6. This guide.
7. Older feature documents and research reports.

Some older documents describe an earlier state in which extraction workers, sharing grants, or production agents were still planned. Verify claims against current code before editing.

## Application in one paragraph

RegBridge is a Python/FastAPI modular monolith backed by PostgreSQL. The browser client is a static HTML/CSS/JavaScript application served by FastAPI. Authentication uses configurable OIDC Authorization Code with PKCE; RegBridge stores application roles and object permissions in PostgreSQL. Project documents are immutable, versioned objects stored in private object storage, with metadata and processing state in PostgreSQL. Regulatory assistance combines authorized project context, Qdrant regulatory retrieval, evidence-sufficiency checks, optional allowlisted official-source retrieval, an interchangeable LLM provider, deterministic verification, and persisted trace-safe run records.

## Repository map

| Path | Purpose |
| --- | --- |
| `app/main.py` | App factory, middleware, router registration, static frontend mount |
| `app/core/` | Configuration, logging, middleware, database and shared runtime concerns |
| `app/<module>/` | Domain router, service, repository, models, contracts, and policies |
| `alembic/versions/` | Ordered database schema migrations |
| `frontend/` | Landing, authentication, entrepreneur, and investor browser applications |
| `tests/` | Backend, contract, security, frontend-source, and integration tests |
| `experiments/` | Controlled research only; never imported by production code |
| `docs/adr/` | Accepted architecture decisions |
| `docs/engineering-research/` | Experiment plans, results, and research decisions |
| `docs/runbooks/` and `docs/operations/` | Operational guidance |

## First five checks for any task

1. Read the Jira ticket, including its research gate and acceptance criteria.
2. Run `git status --short` and preserve unrelated user changes.
3. Locate the existing router, service, repository, contracts, models, and tests before creating anything.
4. Read the relevant security/data documents linked from this guide.
5. Decide the smallest relevant validation suite before editing.

## Non-negotiable constraints

- Do not invent modules, endpoints, roles, database fields, or authorization rules.
- There is no Patent Agent.
- Do not trust token roles or resource IDs as authorization.
- Do not expose ORM entities, storage keys, credentials, private document content, or unrestricted traces.
- Never overwrite a document version or run AI against an unscanned/quarantined version.
- Production code must not import `experiments` or an unapproved orchestration framework.
- Do not commit local `.env` files, secrets, generated reports, benchmark private data, or runtime artifacts.
- A failed experiment is valid; never alter evaluation data merely to produce a preferred result.

## Current delivery context

The repository includes implemented landing/authentication, entrepreneur and investor workspaces, document processing, regulatory Copilot, evidence-aware retrieval, official-source fallback, a derived project knowledge graph, and contract analysis. Researcher backend capabilities exist, but a complete researcher browser workspace is not present. Visual/frontend refinement is an active area, so inspect the working tree before changing shared CSS or JavaScript.

## Quick local start

```powershell
docker compose up -d postgres minio clamav keycloak
python -m pip install -e ".[test]"
alembic upgrade head
python -m uvicorn app.main:app --reload
```

Default local services are documented in [Testing, operations, and troubleshooting](07_TESTING_OPERATIONS_AND_TROUBLESHOOTING.md). Environment values may override all listed ports and providers.

