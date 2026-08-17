# RegBridge

RegBridge is a GenAI platform for the French entrepreneurship, startup, investment, and scientific-research ecosystem.

## Current development state

SCRUM-176 provides technical foundations only: a FastAPI application, typed configuration, PostgreSQL connectivity, a database-backed health endpoint, and modular-monolith boundaries. Business functionality is planned for later tickets.

## Prerequisites

- Python 3.11 or newer
- Docker with Docker Compose

## Local setup

```powershell
Copy-Item .env.example .env
docker compose up -d postgres minio minio-init clamav
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --reload
```

## Health check

With the API running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response: `{"status":"ok","database":"ok"}`

`GET /me` is an authenticated endpoint requiring a configured OIDC bearer access token. See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).

## Tests

```powershell
python -m pytest
```

## Database migrations

With PostgreSQL running and `DATABASE_URL` configured:

```powershell
alembic upgrade head
alembic current
```

See [docs/DATABASE.md](docs/DATABASE.md) for migration and rollback policy.

## Project structure

```text
app/
  main.py       FastAPI bootstrap
  core/         settings and logging
  db/           async SQLAlchemy connectivity
  api/          HTTP routes
  modules/      approved modular-monolith boundaries
tests/          focused automated tests
docs/           architecture and engineering guidance
```

## Architecture

RegBridge V1 is a modular monolith. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Development guide

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for workflow and engineering rules.
