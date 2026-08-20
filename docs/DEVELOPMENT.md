# Development Guide

## Development workflow

Recommended flow: To Do → In Progress → In Review / Verify → Done. Only one major Jira ticket should normally be In Progress at a time.

## Running locally

```powershell
Copy-Item .env.example .env
docker compose up -d postgres
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --reload
```

## Running tests

```powershell
python -m pytest
```

## Environment configuration

Copy `.env.example` to `.env` for local development. `.env` is ignored; `.env.example` is the safe, versioned template. `DATABASE_URL` is required by the typed settings model.

## Authentication development

Configure `OIDC_ISSUER` and `OIDC_AUDIENCE` for protected API use. Authentication tests generate local RSA keys and mock JWKS signing-key retrieval, so they do not require a real identity provider. Run them with `python -m pytest tests/test_authentication.py`. With a configured provider and provisioned database identity, test `/me` using `Authorization: Bearer <access_token>`.

## Adding dependencies

Add runtime dependencies to `[project].dependencies` and test-only dependencies to `[project.optional-dependencies].test` in `pyproject.toml`, then reinstall with `python -m pip install -e ".[test]"`.

## Adding a new module

Add a focused package under `app/modules/`. Keep domain behavior inside its module, keep routes thin, and make cross-domain dependencies explicit. Do not create a service per domain or AI agent.

## Project authorization development

Every project-scoped endpoint must perform object-level authorization after authentication. Authorization must fail closed, and only `project_members.status = active` grants member privileges. Run project authorization tests with `python -m pytest tests/test_authorization.py`. Any permission behavior change requires focused tests, including IDOR and revoked-membership coverage.

## Document development

Start local document infrastructure with `docker compose up -d postgres minio minio-init clamav`. Configure the `OBJECT_STORAGE_*`, `CLAMAV_*`, and `DOCUMENT_MAX_UPLOAD_BYTES` variables from `.env.example`. Run document tests with `python -m pytest tests/test_documents.py`. Never manually edit document versions, place binaries in PostgreSQL, expose storage keys, or allow analyses to omit the exact `document_version_id`.

## Before committing

1. Run relevant tests.
2. Run migrations if the schema changed.
3. Run the full test suite before completing the ticket.

## CI

GitHub Actions runs on pushes to `main` and pull requests targeting `main`. It installs dependencies, applies `alembic upgrade head` to a disposable PostgreSQL 15 database, verifies the Alembic head, runs `python -m pytest -q`, and runs the explicit security regression suite. Any migration, test, or security failure blocks the job. See [CI.md](CI.md).

## Security regressions

Project- and document-authorization changes require negative tests as well as successful-access tests. IDOR, revoked-membership, authentication rejection, and quarantined-document behavior must remain covered.

## Database changes

Business schema changes MUST be introduced through Alembic migrations. Do not manually modify a shared or production database schema.

## Database migrations

Set `DATABASE_URL` using the local `.env` configuration, then run:

```powershell
alembic upgrade head
alembic current
alembic downgrade -1
alembic upgrade head
```

Use `alembic revision --autogenerate -m "describe change"` only for a future migration after reviewing the generated SQL and testing against a disposable PostgreSQL database. Never edit an already-applied migration in a shared environment; roll forward with a new revision.

## Testing rule

Every ticket must add or update tests corresponding to its acceptance criteria.

## Scope discipline

Do not implement future Jira functionality simply because a supporting folder exists.

## Research-oriented engineering workflow

For Jira tickets containing a `Research / Engineering Investigation` section:

1. Read the research question.
2. Create or update the experiment protocol.
3. Define metrics.
4. Define controlled variables.
5. Implement only the experiment or prototype needed.
6. Run it.
7. Record results.
8. Analyze failure cases.
9. Document limitations.
10. Create a research decision.
11. Only then implement the selected production design.

This does not mean every Jira ticket requires research.

## Definition of Done

- implementation complete;
- acceptance criteria verified;
- relevant tests pass;
- documentation updated when behavior or architecture changes;
- no known critical regression;
- no secrets committed.

## Conversation and trace development

SCRUM-182 establishes the framework-neutral persistence boundary for
conversations and execution traces. `agent_runs.id` identifies one run;
`request_id` is a non-unique correlation ID shared by runs caused by one
request. Trace payloads must use allowlisted Pydantic contracts and be
minimized before JSONB persistence. Conversation history is authenticated-only;
anonymous requests do not create persistent threads or messages.

## Production orchestration

SCRUM-183 follows accepted RD-002/ADR-0006: production orchestration is
lightweight, sequential, provider-neutral Python/Pydantic. The deterministic
classifier and router are replaceable through dependency injection. A
ContextBuilder authorizes current project membership before loading a minimal
projection, and agents receive `AgentRequest` DTOs only—never ORM entities,
sessions, tokens, or repositories. Partial agent failures retain successful
results and provenance while SCRUM-182 root/child traces remain correlated.
LangGraph remains optional research-only code and is not imported by
production.

## Next tickets

The immediate sequence is SCRUM-183 onward for research-gated orchestration.
Jira remains the work-tracking source of truth.
