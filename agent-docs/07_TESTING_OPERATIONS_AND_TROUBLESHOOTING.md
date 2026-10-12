# Testing, Operations, and Troubleshooting

## Local services

`docker-compose.yml` defines the development infrastructure:

| Service | Default host address/port | Purpose |
| --- | --- | --- |
| PostgreSQL | `127.0.0.1:25432` in current Compose defaults | Transactional database |
| MinIO API | `127.0.0.1:19000` | Document object storage |
| MinIO console | `127.0.0.1:19001` | Local storage administration |
| ClamAV | `127.0.0.1:3310` | Upload malware scan |
| Keycloak | `127.0.0.1:18080` | Local OIDC provider |
| FastAPI/UI | `127.0.0.1:8000` when Uvicorn uses defaults | API and static frontend |

Environment variables can override ports. Confirm with `docker compose ps` and the effective `.env` rather than assuming.

## Standard setup

```powershell
docker compose up -d postgres minio clamav keycloak
python -m pip install -e ".[test]"
alembic upgrade head
python -m uvicorn app.main:app --reload
```

Useful checks:

```powershell
docker compose ps
alembic current
alembic heads
python -m pytest -q
```

## Validation layers

Choose proportionally, then expand when a shared boundary changes.

1. **Syntax/static source checks** for edited Python/JavaScript.
2. **Focused unit tests** for service/policy/contract behavior.
3. **Negative authorization tests** for object-scoped work.
4. **API integration tests** at the backend boundary.
5. **Migration validation** for model/schema changes.
6. **Browser E2E** for real navigation/session/UI behavior.
7. **Live provider tests** only when explicitly enabled and authorized.
8. **Full regression** before high-risk delivery/merge.

## Test categories and flags

Ordinary tests must not require production/customer services. Live tests are explicitly distinguishable and should remain opt-in. Check the relevant test/module for exact flags; examples in the repository include live experiment/provider and browser-environment gates.

Never silently substitute a mocked result when reporting a live acceptance result.

## Browser validation

The runtime UI is static and served by FastAPI. Browser tests therefore require:

- backend/API serving current code;
- Keycloak reachable and realm/client configuration aligned;
- database migrated and seeded for the intended role/project;
- browser tooling installed;
- supported environment variables enabled.

A skipped browser suite is not an executed acceptance pass. Report it as skipped with the exact reason.

## Common failure: OIDC callback/login

Check, in order:

1. Keycloak container is healthy and discovery URL is reachable.
2. `OIDC_ISSUER` exactly matches token issuer.
3. `OIDC_AUDIENCE` matches the configured API audience.
4. redirect URI and web origin include the actual local host (`127.0.0.1` versus `localhost` matters).
5. callback state/PKCE data remains in the same browser session.
6. database identity linking succeeds for `(issuer, sub)`.
7. no stale static asset is cached in development.

Do not fix login by bypassing validation or trusting email/token roles.

## Common failure: document extraction unavailable

Check:

1. document version state and content type;
2. MinIO object exists and credentials/endpoint are correct;
3. ClamAV is reachable and the version is clean;
4. persisted processing job status/attempt count;
5. worker/runtime process is serving current code;
6. extraction timeout/stale/retry configuration;
7. OCR flag/dependencies only if native extraction cannot satisfy the format.

Retry the persisted job through supported service/API behavior; do not manually mark a document ready.

## Common failure: analysis stays partial/in progress

Check exact `document_version_id`, extracted text availability, analysis/run state, provider flag, provider credentials by presence only, provider timeout/error, structured-output validation, and worker logs with secrets redacted. Provider failure should terminate safely as partial/failed, not remain indefinitely in progress.

## Common failure: Copilot indefinite loader

Inspect both sides:

- browser request, abort controller, polling/SSE behavior, and final UI state;
- API request/run IDs, agent run terminal state, provider timeout, verifier result, and fallback response.

The Stop action must abort the current browser operation and restore controls. It does not authorize deleting persisted history or killing unrelated runs.

## Common failure: Qdrant/provider connectivity

- Verify configured URL/model/collection without printing secrets.
- Confirm the collection exists and embedding dimensions match.
- Distinguish application-side rate limiting from provider HTTP 429.
- Confirm provider base URL follows that provider adapter’s expected API shape.
- Run a minimal abstraction-level check before a full benchmark.

## Migration diagnostics

```powershell
alembic current
alembic heads
alembic upgrade head
alembic check
```

If `alembic check` reports drift, compare SQLAlchemy metadata with migrations. Do not autogenerate and commit unrelated drift without understanding ownership and ticket scope.

## Safe operational reporting

Report:

- command or suite;
- pass/fail/skip counts;
- environment limitations;
- whether live services were actually contacted;
- whether implementation changed;
- genuine blockers.

Never include secret values, tokens, private document bodies, authorization headers, or raw provider payloads.

## Shutdown/restart

Prefer scoped Compose operations:

```powershell
docker compose restart <service>
docker compose down
```

Before terminating host processes, identify exact listening PIDs and ensure they belong to this workspace. Do not broadly kill unrelated user processes.

