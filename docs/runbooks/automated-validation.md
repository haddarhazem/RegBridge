# Automated validation

RegBridge has four deliberately separate validation layers:

| Layer | Execution | External requirements |
| --- | --- | --- |
| Unit | `python -m pytest -q` | None beyond test dependencies |
| Integration | Included in the normal suite | PostgreSQL when the integration tests require it |
| Browser E2E | Python Playwright, explicitly selected | Local PostgreSQL, Keycloak, FastAPI, and MinIO/ClamAV for document journeys |
| Live provider | Pytest, explicit opt-in | Configured provider credentials, outbound network, and provider availability |

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

## Entrepreneur Copilot recovery checks

Keep the current local `.env` and service ports; do not replace them with
historical examples above. Restart the API after changing provider settings.
Use `--no-access-log` with Uvicorn when exercising OIDC redirects so callback
query parameters are not written to access logs. Never print `.env` or tokens.

Ordinary recovery regressions require no live model calls:

```powershell
python -m pytest tests/test_frontend_recovery_behavior.py tests/test_entrepreneur_frontend.py tests/test_entrepreneur_vertical_integration.py tests/test_gemini_provider.py tests/test_scrum184_retrieval.py -q
python -m pytest tests/e2e/browser/test_copilot_recovery.py::test_entrepreneur_pages_idle_history_and_cancel_race -q
```

The browser command requires `BROWSER_E2E_BASE_URL` and the disposable
`BROWSER_E2E_PASSWORD` described above. It uses real local OIDC and persistence;
only the AI response boundary is controlled for cancellation/late-response races.

The explicitly authorized Gemini recovery commands are separate from regression:

```powershell
$env:ENTREPRENEUR_LIVE="1"
python -m pytest tests/test_entrepreneur_recovery_live.py -q
python -m pytest tests/test_entrepreneur_live_copilot.py -q
python -m pytest tests/e2e/browser/test_copilot_recovery.py::test_one_synthetic_enersight_live_browser_turn -q
Remove-Item Env:ENTREPRENEUR_LIVE
```

Run these only with authorization to send synthetic context and the frozen
public regulatory excerpts to the configured provider. No private documents
are used. These are recovery smokes, not provider qualification benchmarks.
The local read-only context audit is separately enabled with
`ENTREPRENEUR_CONTEXT_AUDIT=1` and `tests/test_entrepreneur_context_audit.py`;
it compares stored values with API/ContextBuilder projections without sending
them to a provider.

The recovery run retained the configured Gemini model and set local
`REGULATORY_GENERATION_MAX_TOKENS=4000` and
`REGULATORY_VERIFICATION_MAX_TOKENS=4000`. Defaults remain 900; both settings
are bounded at 4000. A full prompt returned HTTP 200 with an incomplete
generation at the smaller budget. Incomplete output still fails closed;
increasing the bounded budget does not bypass verification. Cost/latency and
quality still require the separate provider qualification gate.

Copilot starts with a fresh transient thread; a persisted conversation is
restored only through **Historique**. Thread creation is lazy on first send.
**Nouvelle conversation**, project changes and logout clear transient state,
not database history. **Arrêter** aborts the browser wait, immediately restores
input, and ignores stale completions. It does not guarantee cancellation of a
running server/Gemini operation: that operation may finish and persist a valid
turn in its original history. No artificial cancellation answer is persisted.

### Entrepreneur feature completion: visibility is not cancellation

The follow-up UX increment supersedes the recovery behavior for close and
same-project navigation. X/Escape hide the Copilot without cancelling its active
generation. Expand/reduce share the same in-memory messages, draft and thread.
Escape first reduces fullscreen, then hides the drawer; only Arrêter explicitly
cancels. Project changes and logout still discard/abort transient project state
for isolation. A response completed while hidden stays in the same thread and
marks the launcher as having an unread answer; it never opens the drawer itself.

```powershell
python -m pytest tests/e2e/browser/test_entrepreneur_features.py tests/e2e/browser/test_copilot_recovery.py -k 'not live_browser' -q
```

This uses real local OIDC and PostgreSQL. Copilot response timing is controlled
at the API boundary; assessment/contract records are synthetic fixtures, not
live model output. Roadmap generation, status updates, history and all fixture
reads go through the real application. Synthetic database-backed documents in
this UI fixture have no object-storage file and must not be used as download or
extraction acceptance evidence. Existing document/contract service tests remain
the source for extraction, analysis and authorization behavior.

Gemini qualification: **DEFERRED**. Current status: **functional development
provider / qualification deferred**. Entrepreneur product completion is the
current priority. Do not run the 20-question, V3 or three-run qualification
experiments as part of these tests; no provider promotion is implied.

Roadmap versions resolve their original assessment relation, not whichever
assessment happens to be newest. Generation requires a completed, non-blocked
assessment. Regulatory source labels are organization-only in the current
public API; the UI renders an HTTP(S) link only if the API actually supplies one.
It does not reconstruct evidence URLs or expose point/conclusion IDs as citations.
Contracts present completed, same-version observations and exact excerpts only;
risks/recommendations intentionally withheld by production are not reconstructed.

CI verifies that the applied revision matches `alembic heads` rather than a
historical hard-coded ticket revision. It still fails when migration execution
fails or the database is behind.
