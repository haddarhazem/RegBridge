# Entrepreneur feature completion — 2026-09-12

## Scope and deferred research

Gemini remains a functional development provider. Qualification is **DEFERRED**
because Entrepreneur product completion is the current priority. No 20-question,
V3 or three-run qualification experiment, live provider call, Jira update, commit
or push was performed in this increment. The earlier recovery report remains
historical; this increment explicitly supersedes its close/navigation semantics.

## Changes

- Copilot visibility, drawer/fullscreen mode and request/thread state are separate.
  X hides without aborting. Escape reduces fullscreen, then hides the drawer.
  Messages and in-memory drafts survive toggles and same-project navigation.
  Hidden completion marks the launcher without opening the panel or stealing focus.
  Arrêter still aborts the browser request and rejects stale results. Project
  changes/logout still reset transient state; PostgreSQL history is retained.
  Pending requests capture their document context at submission rather than
  reading a newly selected page's context later.
- Roadmap uses the existing generation/version/status contracts. Missing or
  blocked assessments are explained. Items show ordered steps, exact supported
  statuses, dependencies by title and their original assessment conclusions.
  Historical roadmap source versions are resolved independently of the latest
  assessment. No dates, authorities or legal requirements are invented.
- Réglementation presents latest/version history, timestamps, verification state,
  obligations, recommended actions, coverage gaps and public source labels.
  No verdict is presented as legal certification.
- Contrats reuses Documents and immutable versions. Only clean, text-ready versions
  can be selected. Completed observations must match the analyzed version and have
  an evidence span. Failed/running/unavailable states are explicit; withheld legal
  risks/recommendations are never reconstructed. Version/title, exact excerpt,
  category, character location and analysis date remain visible.
- A real browser status update exposed a pre-existing Roadmap response bug:
  SQLAlchemy expired the server-generated updated_at value and synchronous DTO
  serialization raised MissingGreenlet after the write. The endpoint now awaits
  refresh of that attribute. No migration/model or authorization change was made.

## Contracts and limits

Roadmap: GET list/latest/version, POST with regulatory_assessment_id, PATCH item
status (pending/in_progress/completed/skipped). Generation requires completed and
non-blocked assessment. Assessment: GET list/latest/version and explicit POST;
public result categories are obligations/recommendations/uncertainties.
Contracts: document -> immutable version -> analysis, exposing observations with
version IDs and exact spans internally, not automated semantic advice.

Public assessment sources are organization strings; real evidence URLs are not
exposed by the present production response. The renderer supports a safe HTTP(S)
URL when supplied but does not invent one. This is a backend contract limitation,
not evidence that real assessment URLs were exercised in browser acceptance.
Contract production provider behavior remains unchanged (its existing Mistral
path was not switched to Gemini). No private document was sent to any provider.
Server/upstream cancellation after Arrêter remains unguaranteed.

## Validation

- Baseline selected frontend/context/provider tests: 26 passed.
- Focused frontend, Roadmap, assessment, contract, documents, Copilot/context,
  provider and auth tests: 71 passed.
- Roadmap/assessment/contract regression after the timestamp fix: 11 passed.
- Executable Node frontend contracts: 6 passed, including malformed/null roadmap,
  linked version provenance, source-link safety, failed and wrong-version findings.
- Real browser: 6 passed, 1 live-provider case deliberately deselected. Real OIDC
  and project persistence; controlled Copilot response timing; real Roadmap
  generation/status/history/reload; synthetic assessment/contract rows read through
  real endpoints. The seeded records are not presented as new live AI output.
- Full regression after the backend fix: 363 passed, 21 opt-in skips.
- Python compilation, frontend JS syntax, production-to-experiments import audit,
  known-secret scan and git diff --check: passed.
- Desktop 1440x900 and mobile 390x844 Copilot screenshots inspected; controls remain
  visible, no horizontal overflow; browser acceptance recorded no uncaught JS errors.

Commands include:

```powershell
python -m pytest tests/e2e/browser/test_entrepreneur_features.py tests/e2e/browser/test_copilot_recovery.py -k 'not live_browser' -q -p no:cacheprovider --tb=short
python -m pytest tests/test_scrum190_roadmap.py tests/test_scrum189_assessment.py tests/test_scrum193_contract_analysis.py -q -p no:cacheprovider --tb=short
python -m pytest -q -p no:cacheprovider --basetemp $featureTemp --tb=short
node --test tests/frontend-recovery.test.cjs
python -m compileall -q app
node --check frontend/entrepreneur/app.js
node --check frontend/entrepreneur/views.js
node --check frontend/entrepreneur/api.js
git diff --check
```

Browser commands use the existing local base URL and disposable synthetic password
environment variables. featureTemp is a newly generated temporary directory.
Only synthetic fixture records are written; original user projects/history are
unchanged. Prior staged recovery changes remain staged; this increment was not
staged or committed.
