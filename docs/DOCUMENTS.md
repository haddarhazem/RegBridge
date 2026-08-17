# Document Management

## Architecture

```text
PostgreSQL → metadata, status, versions, and checksums
Object storage → private binary files
```

PostgreSQL contains no document binary or base64 content. The application uses an S3-compatible object-storage port. Local development uses private MinIO; production storage must provide encryption at rest and TLS for remote connections. The production provider and KMS strategy remain configurable.

## Data model

- `documents` → logical document and current-version metadata
- `document_versions` → immutable binary references and checksums
- `document_processing_jobs` → idempotent references to exact immutable versions

## Upload flow

The backend authenticates and reuses SCRUM-179 project authorization, stages the upload in bounded chunks, enforces `DOCUMENT_MAX_UPLOAD_BYTES`, computes SHA-256, validates real file content, generates an opaque storage key, stores the binary privately, and scans it before marking it clean.

If the database transaction fails after object storage succeeds, the service attempts compensating object deletion. Complete atomicity across PostgreSQL and object storage is not assumed; residual orphan cleanup remains an operational concern.

## Versioning

The first upload creates version 1. A replacement creates a new `document_versions` row with the next version number and updates `documents.current_version_id` only when the new version is clean. Existing versions are never overwritten.

## Classification

Exact V2.1 values:

- `public`
- `internal`
- `confidential`
- `highly_confidential`

## Visibility

Exact V2.1 values:

- `private`
- `project_members`
- `shared`
- `public`

`shared` is fail-closed because `project_access_grants` is deferred. There is no anonymous public binary-download endpoint; backend authentication and authorization remain required.

## Malware

The local adapter speaks ClamAV's streaming protocol. Results are `clean`, `infected`, or `error`. Infected and scanner-error uploads are quarantined or remain non-current and cannot be downloaded or used for processing. No always-clean runtime fallback exists.

## Deletion

Document deletion sets `deleted_at`. Normal metadata, version, download, and processing-job access excludes logically deleted documents. Physical purge is a future controlled operation.

## Processing

Processing jobs reference one immutable `document_version_id` and enforce unique `idempotency_key`. This ticket persists job requests only; workers, OCR, extraction, embeddings, and AI pipelines are not implemented.

## Security

- private object storage;
- no public bucket or direct object URL exposure;
- backend authorization before metadata/download access;
- server-side size/type validation and SHA-256;
- no quarantined or unscanned version enters processing;
- storage keys are backend-generated;
- no binary content in PostgreSQL, logs, or audit metadata.
