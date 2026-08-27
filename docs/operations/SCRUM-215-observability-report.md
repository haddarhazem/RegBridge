# SCRUM-215 — Observability + Operational Readiness Final Report

## Baseline

- Initial command: `python -m pytest -q`
- Initial result: 275 collected/passed, 0 failed, 0 skipped, 47.60 s.
- Migration head: `scrum212_grant_reissue`.

## Research identity

- RQ: `RQ-028-minimum-observability`
- EX: `EX-028`
- RD: `RD-024-minimum-observability`
- Status: FINAL
- Candidates: O0 structured logs + bounded metrics + existing correlation;
  O1 adds explicit span context.
- Selected: O0
- Evidence: STRONG for the frozen synthetic failure benchmark.

## Research gates

| Gate | O0 | O1 |
|---|---:|---:|
| Critical failure detection | 100% (8/8) | 100% (8/8) |
| Root-cause localization | 100% (8/8) | 100% (8/8) |
| Request/run correlation | 100% | 100% |
| Private-content leakage | 0 | 0 |
| Secret leakage | 0 | 0 |
| Non-actionable alerts | 0 | 0 |
| Median signal events | 3 | 4 |

F9 worker failure is `NOT_APPLICABLE`: the current release has no production
worker or queue. O0 satisfies all hard gates and O1 provides no measurable
improvement. Research gate: PASS.

## Production signals

Structured operational events and bounded metrics cover HTTP, PostgreSQL,
Qdrant, object storage, Mistral, agent runs and orchestration. Existing
`request_id`, `run_id` and `parent_run_id` semantics are reused. Metrics do not
use user, project, document, request, prompt or source URL labels.

`/metrics` exposes aggregates only. The health endpoint remains unchanged in
its public contract. No vendor dependency or dashboard was added.

## Privacy and security

Synthetic sentinel tests confirm zero leakage of private document/RAG values,
API keys, bearer tokens and private context in observability events and metric
snapshots. No private or production data was used. Audit logs remain separate
from operational events.

## Failure coverage and runbooks

F1 PostgreSQL, F2 Qdrant, F3 storage, F4/F5/F6 Mistral, F7 RAG/agent timeout
and F8 partial GenAI failure are detected and localized. F9 is not applicable.
Runbooks: `docs/runbooks/postgresql.md`, `qdrant.md`, `storage.md`,
`llm-provider.md`, `partial-genai.md` and `worker.md`. Priority alert defaults
and privacy rules are in `docs/runbooks/alerts.md`.

## Tests and quality

- SCRUM-215 observability and EX-028 tests: 6 passed.
- Prior trace/provider/retrieval/health tests: 29 passed.
- Full regression after productionization: 280 passed.
- Compilation: PASS.
- Fresh imports: PASS.
- Production → experiments boundary: PASS.
- Secret/privacy scan: PASS.
- `git diff --check`: PASS.
- `python -m alembic upgrade head`: PASS.
- `python -m alembic check`: known unrelated historical drift only; no SCRUM-215
  schema change was introduced.

## Scope

SCRUM-196 regulatory watch: `FUTURE_PERSPECTIVE / POST-MVP / OUT_OF_CURRENT_RELEASE_SCOPE`.
It has no SCRUM-215 test obligation and does not block release. SCRUM-216
backup/recovery and SCRUM-217 deployment/release remain outside this ticket.

## Verdict

- A. Metrics/logs: PASS
- B. End-to-end correlation: PASS
- C. Runbooks: PASS
- D. Actionable privacy-safe alerts: PASS
- SCRUM-215 complete: YES
- Ready to commit: YES
- Release blocked: NO
