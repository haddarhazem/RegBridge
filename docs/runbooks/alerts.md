# Priority operational alerts

These are initial operational defaults, not traffic-optimized thresholds.
Alert payloads contain only bounded aggregate labels and a runbook link.

| Alert | Initial condition | Impact | First action | Runbook |
|---|---|---|---|---|
| PostgreSQL unavailable | health failure or dependency error | requests needing persistence may fail | check database reachability and migration head | `postgresql.md` |
| Qdrant unavailable | Qdrant error rate above 0 for 5 minutes | regulatory answers may degrade/fail | verify read-only collection reachability | `qdrant.md` |
| Storage failure | storage error rate above 0 for 5 minutes | document read/write may fail | check endpoint and bucket configuration | `storage.md` |
| LLM provider failure | provider error/rate-limit signal above 0 for 5 minutes | generated explanations may fall back/fail | inspect bounded provider category and retry safely | `llm-provider.md` |
| GenAI run failures | failed agent runs above 0 for 5 minutes | workflow may be partial | follow request/run hierarchy and retry failed boundary | `partial-genai.md` |

No alert is defined for SCRUM-196 regulatory watch or for workers because
those are outside the current release/current architecture. Alerts never
contain prompts, document text, RAG chunks, tokens, API keys, private contact
data or raw provider responses.
