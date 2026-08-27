# RD-024 — Select minimum production observability

## Status

FINAL

## Selected strategy

O0: vendor-neutral structured operational events, bounded in-process metrics,
and the existing SCRUM-182 request/run correlation.

## Evidence

EX-028 detected and localized 8/8 applicable frozen failures, with 100%
correlation coverage, zero private-content leakage, zero secret leakage and
zero non-actionable alerts. O1 did not improve any hard-gate metric and used
one additional median signal event.

## Production consequence

The application uses `request_id`, `run_id` and `parent_run_id` in structured
events and existing agent-run persistence. Metrics expose only bounded labels:
component, operation, status, dependency, error category and route template.
No vendor exporter or worker was added. `/metrics` contains aggregates only.

## Scope exclusions

SCRUM-196 regulatory watch remains `FUTURE_PERSPECTIVE / POST-MVP` and is not
instrumented. SCRUM-216 backup/recovery and SCRUM-217 release deployment remain
outside this ticket.
