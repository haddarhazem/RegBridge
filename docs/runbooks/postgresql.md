# PostgreSQL unavailable

**Symptom:** `dependency=postgresql`, `status=error`, or `/health` returns 503.

**First check:** inspect `regbridge_dependency_calls_total` and the application
environment's database reachability. Never print the DSN or credentials.

**Recovery:** verify the supported PostgreSQL service is running, connectivity
and migration head, then retry the health check. Escalate persistent pool or
authentication failures to the database owner. Follow SCRUM-216 for recovery;
do not restore data from this runbook.

**Verify:** `/health` reports database `ok` and the error rate returns to zero.
