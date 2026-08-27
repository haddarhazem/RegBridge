# SCRUM-214 Test Completion Report

## Scope

This report records the final requirements-driven automated validation for the
current release. It excludes SCRUM-196, which is
`FUTURE_PERSPECTIVE / POST-MVP / OUT_OF_CURRENT_RELEASE_SCOPE`.

## Baseline

- Command: `python -m pytest -q`
- Initial collected/passed: 275 / 275
- Initial failed/skipped/xfail: 0 / 0 / 0
- Duration: 46.91 seconds
- Database migration head: `scrum212_grant_reissue`

The baseline was green before SCRUM-214 changes. No baseline defect was
silently attributed to this ticket.

## Test environment and data

- PostgreSQL: repository Docker service, database URL from `.env`.
- Migrations: `python -m alembic upgrade head`.
- Fixtures: generated UUIDs, unique synthetic users/projects, and generated
  PDF/DOCX/TXT content where applicable.
- Production/private data: not used.
- Real contract/research paper: not required for the deterministic suite.
- Live provider/Qdrant: optional only; not required by CI.

## Validation evidence

The complete mapping is in
[`SCRUM-214-requirements-test-matrix.md`](SCRUM-214-requirements-test-matrix.md).
It covers the five actor journeys, implemented API contracts and IDOR checks,
deterministic calculation/verification components, persistence/versioning,
auditing, provider failure behavior and security regressions.

The release-critical suite is explicit in `.github/workflows/ci.yml`, runs after
clean migrations, and is followed by the full suite and security suite. Pytest
exit status propagates directly to CI.

## External and storage limitations

Frozen Qdrant and live LLM smoke tests remain optional local checks. CI does not
require external credentials. File tests use supported deterministic adapters;
no unsupported formats or private documents were introduced.

## Alembic

`python -m alembic upgrade head` succeeds at `scrum212_grant_reissue`.
`alembic check` may report the known historical unrelated drift in audit
indexes, document-version constraints, the users email index and table
comments. SCRUM-214 does not alter that drift.

## SCRUM-196 exclusion

Regulatory watch is intentionally POST-MVP. There is no current-release
obligation for polling, daily updates, change detection, impact analysis or
notifications, and it does not affect SCRUM-214 PASS/FAIL calculations.

## Final execution evidence

- `python -m pytest -q`: 275 passed, 0 failed, 0 skipped, 43.84 seconds.
- Release-critical suite: 51 passed on run 1 (13.57 seconds) and 51 passed
  on run 2 (12.61 seconds).
- `python -m alembic upgrade head`: PASS.
- `python -m compileall -q app tests experiments`: PASS.
- Production-to-experiments import audit: PASS; no production module imports
  experiment implementations.
- Secret/privacy scan: PASS; only test fixtures and redaction assertions
  contain sentinel secret strings, and no credential value is exposed.
- `git diff --check`: PASS.
- `python -m alembic check`: FAIL only for the documented historical drift:
  audit index ordering, the document-version unique constraint, the users
  email index and the users table comment. No SCRUM-214 schema change or
  migration was introduced.

## Final gate

The current-release test suite is green, the critical suite is explicit in CI
and stable across two sequential runs, and the repository has no unresolved
current-release test regression. The known Alembic drift is unrelated and was
not changed by SCRUM-214.
