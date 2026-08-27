# Qdrant unavailable

**Symptom:** dependency event for `qdrant` is `error`, with `RAG_ERROR` or
`DEPENDENCY_UNAVAILABLE`.

**First check:** Qdrant reachability, collection availability and the read-only
configuration. Do not log vectors or retrieved content.

**Recovery:** retry after the service recovers or use the current documented
safe regulatory failure behavior. Never recreate, delete, upsert or rechunk the
frozen `reglementation_chunks` collection. Escalate persistent errors.

**Verify:** a controlled regulatory query returns usable evidence.
