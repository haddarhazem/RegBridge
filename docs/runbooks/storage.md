# Object storage unavailable

**Symptom:** `object_storage` read/write/delete dependency event is `error` or
`STORAGE_ERROR`.

**First check:** endpoint reachability, bucket configuration and the safe
document/version identifier. Never log content or storage credentials.

**Recovery:** restore service/configuration and retry the operation according
to its idempotency behavior. Do not silently replace or regenerate a user
document. Escalate checksum/integrity failures; SCRUM-216 owns recovery.

**Verify:** authorized access succeeds and checksum metadata remains unchanged.
