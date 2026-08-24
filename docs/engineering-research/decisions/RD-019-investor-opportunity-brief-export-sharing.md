# RD-019 — Investor Opportunity Brief Export and Sharing

## Decision

SCRUM-207 exports only an immutable Investor Opportunity Brief version that
is both `APPROVED` and backed by an exact `VERIFIED` verification run. PDF
generation is deterministic and uses only the persisted five-section public
content; no LLM call is made during export.

Sharing reuses the SCRUM-197 `investor_share_grants` table with resource type
`INVESTOR_OPPORTUNITY_BRIEF_VERSION`, the exact version as `resource_id`, an
explicit RegBridge recipient, and `READ` scope. There are no public links,
anonymous access paths, email attachments, or automatic sharing of newer
versions. Revocation is enforced on both the view and PDF endpoints.

## Authorization and audit

The brief owner may export, create, inspect, and revoke a grant. A recipient
may view and download only the exact active grant. Every export, share,
recipient access, and revocation writes an audit event containing identifiers
and safe export metadata only; PDF content, secrets, and private snapshots
are not logged.

## Consequences

PDF bytes are reproducible for the same approved version and can be checked
by SHA-256. Revocation prevents future downloads but cannot recall a file a
recipient has already downloaded. A later draft or sibling version is not
implicitly accessible through an older grant.
