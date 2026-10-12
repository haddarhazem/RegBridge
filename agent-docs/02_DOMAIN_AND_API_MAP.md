# Domain and API Map

This is a navigation map, not an exhaustive OpenAPI listing. Inspect the router and contracts before changing an endpoint.

## Identity

**Purpose:** OIDC identity linking, current-user projection, database-controlled business roles, and security audit records.

**Core records:** `users`, `user_identities`, `roles`, `user_roles`, `audit_logs`.

**Representative endpoints:**

- `GET /auth/config`
- `GET /me`
- `GET /me/roles/options`
- role selection under `/me/roles`

**Important:** `(issuer, subject)` is the external identity key. Email is not the stable identity key. Token roles are not RegBridge authorization.

## Projects

**Purpose:** startup/project lifecycle, typed project facts, membership, startup profiles, research needs, and the derived knowledge graph.

**Core records:** `projects`, `project_facts`, `project_members`, startup profile/revision tables, research-need tables.

**Representative endpoints:**

- project collection/detail routes under `/projects`
- `/projects/{project_id}/facts`
- `/projects/{project_id}/graph`
- `/projects/{project_id}/members`
- project profile and research-need routes

**Important:** only active membership grants member access. Project facts carry provenance and confirmation state; pending/deleted facts must not become trusted context.

## Documents and contracts

**Purpose:** document metadata, immutable versions, private binary storage, scan/extraction jobs, downloads, and exact-version contract analysis.

**Core records:** `documents`, `document_versions`, `document_processing_jobs`, `contract_analyses`, `contract_clauses`.

**Representative endpoints:**

- `POST /projects/{project_id}/documents`
- document/version routes under `/documents`
- processing job/retry routes
- exact-version contract-analysis routes

**Important:** every AI or analysis result references an exact `document_version_id`. Files remain in object storage, not PostgreSQL.

## Regulatory and compliance

**Purpose:** regulatory evidence retrieval, project assessments, launch roadmaps, control frameworks, evidence linking, and compliance scoring.

**Core records:** assessment input snapshots, regulatory assessments, launch roadmaps/items, compliance framework/version/control/adoption/project-control/evidence/link/score tables.

**Representative endpoints:**

- regulatory retrieval/assessment routes
- project assessment and roadmap routes
- `GET /compliance/frameworks`
- project compliance routes under `/projects/{project_id}/compliance`

**Important:** roadmap and compliance output are evidence-linked aids, not legal certification. Do not claim real-time regulatory surveillance unless a ticket explicitly implements and proves it.

## AI and conversations

**Purpose:** authenticated conversation history, Copilot requests, typed agent orchestration, request correlation, and trace-safe observability.

**Core records:** `conversation_threads`, `conversation_messages`, `agent_runs`.

**Representative endpoints:**

- `/conversations`
- thread message/response routes
- request/run-status routes

**Important:** ContextBuilder authorizes before loading. Agents receive minimized DTOs and never tokens, sessions, repositories, or ORM entities.

## Investment

**Purpose:** investor profiles/theses, visibility-aware startup discovery, opportunities, matching, briefs, events, controlled contact, and investor read views.

**Core records:** investor profile/thesis versions, opportunity versions, matching runs/results, brief runs/versions/verifications/claims, events/registrations, contact requests/consents.

**Representative endpoints:**

- `/startups/search`
- `/investment-opportunities`
- `/investment-matches`
- `/investment-briefs`
- `/events`
- `/contact-requests`
- `/investor/matches`
- `/investor/briefs`

**Important:** deterministic scores, dimensions, reason codes, method/version, and snapshot IDs remain authoritative. An LLM may explain validated structure but must not rewrite it.

## Research

**Purpose:** researcher profiles, private versioned deposits, evidence-locked extraction, author approval, controlled access/collaboration, and approved-snapshot startup matching.

**Core records:** research profiles, outputs/versions, extractions/items/evidence, discoveries/versions, access requests/grants, research match runs/results.

**Representative endpoints:**

- `/researcher/profile`
- `/research/outputs`
- discovery approval routes
- research access-request routes

**Important:** research discovery must not invent applications or opportunities. Publication is author-controlled, and matching uses approved immutable snapshots.

## Sharing

**Purpose:** explicit resource-level access grants and controlled resource resolution.

**Representative endpoints:**

- `/projects/{project_id}/shares`
- `/shared/{grant_id}/resource`

**Important:** `shared` visibility fails closed without a valid explicit grant. A grant does not imply broader project membership.

## Router registration

`app/main.py` is the definitive list of active routers. When adding a route:

1. extend the existing domain router;
2. keep validation in Pydantic contracts;
3. invoke a service;
4. enforce authentication and object authorization;
5. add positive and negative tests;
6. register a new router in `main.py` only when an existing router cannot own the capability.

## Capability-to-Jira lineage

The current implementation history runs from core architecture and auth through project/document/security work, followed by investment, research, validation, observability, and frontend/runtime increments. Recent traceability tickets cover:

- landing and authentication frontend;
- entrepreneur, compliance, and investor workspaces;
- document extraction;
- LLM runtime/demo behavior;
- roadmap semantics;
- evidence-aware Copilot and official-source fallback;
- project knowledge graph;
- contract analysis V2;
- V1.3 frontend redesign.

Use Jira for exact acceptance criteria and status. Do not infer ticket completion from the presence of code alone.

