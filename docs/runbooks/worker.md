# Document extraction worker

Document uploads create an idempotent `extract_text` job after a clean
malware scan. The upload endpoint schedules the small PostgreSQL-backed worker
as a FastAPI background task, so HTTP upload responses do not wait for native
extraction or OCR.

The worker claims jobs with `FOR UPDATE SKIP LOCKED`, stores only deterministic
extraction metadata, and can recover stale `running` jobs. Failed jobs are
retryable through the authenticated document retry endpoint until the
configured attempt limit is reached.

Native extraction supports PDF, DOCX, and UTF-8 TXT. Mistral OCR is used only
when native extraction is insufficient and
`DOCUMENT_EXTERNAL_PROCESSING_ENABLED=true` is explicitly configured. OCR is
opt-in and the uploaded provider file is deleted after processing.

Operational settings:

- `DOCUMENT_EXTRACTION_STALE_AFTER_SECONDS`
- `DOCUMENT_EXTRACTION_MAX_ATTEMPTS`
- `DOCUMENT_EXTRACTION_CONCURRENCY` (for deployments running multiple worker
  instances)
- `DOCUMENT_EXTERNAL_PROCESSING_ENABLED`

The worker never exposes document text, storage keys, provider credentials, or
provider response payloads in logs or API responses. Contract analysis and
Copilot context accept only versions whose extraction status is `ready`.
