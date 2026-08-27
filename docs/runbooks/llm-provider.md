# LLM provider unavailable

**Symptom:** `mistral` dependency event is `error`, including timeout, 429,
`DEPENDENCY_UNAVAILABLE` or `INVALID_PROVIDER_RESPONSE`.

**First check:** provider status/configuration, bounded error category and
retry count. Never log API keys, prompts, private context or raw completions.

**Recovery:** apply the operation's existing safe fallback (reduced
deterministic result where supported), otherwise return the documented safe
failure. Retry timeouts/rate limits with bounded policy only; escalate repeated
authentication/configuration failures.

**Verify:** provider calls succeed and token/cost metadata remains non-secret.
