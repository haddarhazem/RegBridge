# ADR-0003: Store document binaries outside PostgreSQL

Status: Accepted

## Context

RegBridge handles PDF, DOCX, and TXT files with potentially many versions. PostgreSQL should remain the business metadata source of truth without binary-content bloat, and the storage provider may change.

## Decision

Document binaries are stored in private object storage. PostgreSQL stores metadata, checksums, statuses, and immutable version references. Application code uses an object-storage adapter. Local development uses S3-compatible MinIO; production storage must provide encryption at rest and TLS.

## Consequences

Positive: scalable binary storage, smaller relational backups, replaceable providers, and explicit immutable object/version mapping.

Trade-offs: PostgreSQL and object storage require compensation for partial failure, backups involve two systems, and encryption/lifecycle settings require operational configuration.
