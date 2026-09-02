# Automated validation

RegBridge has four deliberately separate validation layers:

| Layer | Execution | External requirements |
| --- | --- | --- |
| Unit | `python -m pytest -q` | None beyond test dependencies |
| Integration | Included in the normal suite | PostgreSQL when the integration tests require it |
| Browser E2E | Python Playwright, explicitly selected | Local PostgreSQL, Keycloak, FastAPI, and MinIO/ClamAV for document journeys |
| Live provider | Pytest, explicit opt-in | Mistral credentials, outbound network, and provider availability |

## Real-browser journeys

Install the single browser framework used by the repository and Chromium:

```powershell
python -m pip install -e ".[test,browser]"
python -m playwright install chromium
```

Use the existing local services and application commands:

The Compose file keeps Docker-internal endpoints unchanged and uses stable,
configurable localhost ports for Windows development:

```powershell
$env:POSTGRES_HOST_PORT="25432"
$env:MINIO_API_HOST_PORT="19000"
$env:MINIO_CONSOLE_HOST_PORT="19001"
$env:DATABASE_URL="postgresql+asyncpg://regbridge:regbridge@127.0.0.1:25432/regbridge"
$env:OBJECT_STORAGE_ENDPOINT="http://127.0.0.1:19000"
```

```powershell
docker compose up -d postgres minio minio-init clamav keycloak
$env:OIDC_ISSUER="http://127.0.0.1:18080/realms/regbridge"
$env:OIDC_AUDIENCE="regbridge-api"
$env:OIDC_CLIENT_ID="regbridge-frontend"
$env:OIDC_REDIRECT_URI="http://127.0.0.1:8000/auth/callback/"
$env:OIDC_POST_LOGOUT_REDIRECT_URI="http://127.0.0.1:8000/auth/login/"
alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, provide a synthetic-only password and run the suite:

```powershell
$env:BROWSER_E2E_BASE_URL="http://127.0.0.1:8000"
$env:BROWSER_E2E_PASSWORD="<synthetic-test-password>"
python -m pytest tests/e2e/browser -m browser_e2e -q
```

The tests register unique synthetic users through the real Keycloak browser
flow. They do not inject bearer tokens or use production/private data. Failure
screenshots and traces are written only to the ignored
`artifacts/browser-e2e/` directory.

The current browser harness covers the entrepreneur critical journey, logout /
relogin persistence, cross-project denial, native TXT extraction, and the
implemented compliance journey. Investor browser coverage remains pending the
investor frontend.

## Live Mistral smoke tests

Live provider calls are automated but never part of normal regression. They
require both an explicit opt-in and a local `.env`/environment credential:

```powershell
$env:RUN_LIVE_PROVIDER_TESTS="1"
python -m pytest tests/live_provider -m live_provider -q
```

The suite checks one minimal Mistral generation response and one synthetic
scanned-PDF OCR response through the existing provider abstractions. Missing
opt-in or credentials produces an intentional skip. Network, authentication,
rate-limit, provider-5xx, and invalid-response failures are classified without
printing provider messages, prompts, document text, keys, or authorization
headers. A provider outage is reported as a blocked live smoke, never as an
application success.

The `browser-e2e` GitHub Actions workflow runs the browser suite separately
from normal CI. Its `BROWSER_E2E_PASSWORD` value must be a disposable CI
secret; the live-provider suite remains a separately controlled command and
does not block ordinary pull-request regression.
