# Continuous Integration

## Purpose

CI proves every pull request and push to `main` can install RegBridge from a clean environment, build a fresh database through Alembic, and pass the automated security regression suite.

## Triggers

The GitHub Actions workflow runs on:

- pull requests targeting `main`;
- pushes to `main`.

## Pipeline

```text
checkout
  → Python 3.12
  → dependency installation
  → ephemeral PostgreSQL 15
  → alembic upgrade head
  → alembic current/head verification
  → full pytest suite
  → security regression tests
```

Migration and test failures fail the job. No step uses `continue-on-error` or suppresses errors.

## Environment

CI uses a disposable PostgreSQL service with the test-only database `regbridge_ci` and test-only credentials. The current unit/security suite uses deterministic local JWT, storage, and malware-scanner fakes, so MinIO and ClamAV are not required for the normal CI job.

## Production isolation

CI never uses `.env`, production databases, production buckets, production OIDC providers, production API keys, or customer data. All configured service values are safe ephemeral examples.

## Migration gate

The job runs:

```bash
alembic upgrade head
alembic current
```

before pytest. The current head must be `scrum190_roadmaps`.

## Security gates

The suite explicitly covers project and document IDOR protection, invited/revoked membership behavior, viewer restrictions, authentication rejection, quarantine/fail-closed behavior, storage-key safety, and audit metadata.

## Debugging failures

Reproduce the main gates locally with:

```powershell
Copy-Item .env.example .env
docker compose up -d postgres
python -m pip install -e ".[test]"
alembic upgrade head
alembic current
python -m pytest -q
python -m pytest -q tests/test_security_regressions.py
```

The local PostgreSQL, MinIO, and ClamAV services are disposable development infrastructure. The normal CI suite does not require cloud credentials or production services.
