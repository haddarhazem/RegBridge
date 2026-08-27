# Worker / async failure

**Status:** `NOT APPLICABLE — no production worker or queue exists in the
current release.` Document processing jobs are persisted requests, not a
running worker component. No worker metrics or fake recovery procedure is
claimed by SCRUM-215.

If a future worker is introduced, it requires a separately approved design and
runbook covering retries, backlog and idempotency.
