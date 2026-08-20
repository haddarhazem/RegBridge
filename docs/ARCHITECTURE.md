# Architecture

## Architectural style

RegBridge V1 is a modular monolith: one deployable FastAPI backend with internally isolated domains. This keeps development, testing, local setup, and transactions simple for the current team. A domain may be extracted later if operational evidence justifies it; AI agents are logical capabilities, not automatically separate services.

## Backend modules

- `identity`: identity and authentication-related domain (planned)
- `projects`: entrepreneur/startup project lifecycle (planned)
- `documents`: file metadata, version, and access infrastructure (planned)
- `regulatory`: regulatory guidance and assessments (planned)
- `compliance`: controls, evidence, and scoring (planned)
- `investment`: investors, opportunities, and matching (planned)
- `research`: research discovery, approved abstracts, and collaboration (planned)
- `ai`: model orchestration, agent contracts, and verification infrastructure (planned)

Implemented in SCRUM-176: application bootstrap, configuration, database connectivity, health endpoint, and module boundaries. Implemented in SCRUM-177: the V2.1 identity, project, membership, and audit foundation models and Alembic migration. Implemented in SCRUM-178: provider-neutral JWT/OIDC validation, business identity mapping, database-controlled global roles, authenticated-principal contracts, and the protected `/me` route. Project-level authorization, document authorization, sharing grants, and admin role management remain planned.

SCRUM-179 implements the project service/repository foundation, project membership lifecycle, project-level authorization, member-role authorization, project visibility enforcement, and audit of membership/security changes. SCRUM-180 implements document metadata, immutable versions, processing-job persistence, object-storage abstraction, secure upload validation, checksums, document authorization, malware scanning gates, and soft deletion. Full extraction workers, OCR, embeddings, explicit sharing grants, and retention automation remain planned.

SCRUM-181 implements the automated CI baseline, clean-database migration gate, access-control regression suite, and audit verification baseline. SCRUM-182 implements authenticated conversation persistence, request-correlated agent-run tracing, parent/child run semantics, and allowlisted trace-safe contracts. SCRUM-183 implements the accepted lightweight Python/Pydantic orchestration foundation with explicit deterministic routing, authorization-before-context loading, minimized DTOs, structured aggregation, and SCRUM-182 trace integration. LangGraph was evaluated in EX-001 but is not a V1 production dependency. RAG, verification, monitoring, and AI observability remain future scope.

## Dependency direction

- API routes call application/domain services.
- Business modules do not import HTTP concerns.
- Database access remains behind infrastructure/repository layers.
- Future AI agents receive explicit validated model input, not raw SQLAlchemy entities.
- Conversation and agent-run persistence is accessed through focused repositories and services; trace JSONB is produced only from explicit Pydantic projections.
- Production orchestration uses explicit Python/Pydantic control flow. ContextBuilder authorization precedes sensitive projection loading, and agents receive validated minimized DTOs rather than ORM entities.
- Cross-domain imports are deliberate rather than arbitrary.

## Infrastructure

Implemented: FastAPI, PostgreSQL 15, SQLAlchemy async with asyncpg, and an S3-compatible private object-storage adapter with local MinIO configuration. Qdrant and AI/document-processing pipelines remain future infrastructure.

## Security baseline

Configuration is environment-based. Local environment files are ignored and no credentials are committed. Connection details are never returned by the health endpoint or logged.
