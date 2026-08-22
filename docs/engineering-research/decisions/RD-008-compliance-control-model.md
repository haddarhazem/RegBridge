# RD-008 — Compliance control model

Status: ACCEPTED
Ticket: SCRUM-194
Research: EX-013 / RQ-012

## Decision

Use materialized project compliance controls. Frameworks, immutable framework
versions, and control definitions are reference data. A project adoption
creates project-owned controls bound to the exact framework version and
control definition. Framework upgrades are explicit and audited; publishing a
new framework version never rewrites prior project state.

Evidence is project-scoped and may reference an immutable `DocumentVersion`
or a bounded structured declaration. Evidence has explicit ACTIVE/REVOKED
state. Revoked evidence is excluded from current active counts while its
historical state remains queryable.

## Rejected alternative

Dynamic project controls were rejected because current framework definitions
can alter historical views, and dynamic evidence correlation can fail
revocation and isolation invariants.

## Scope and limitations

GDPR/RGPD and EU AI Act are represented as independent extensible framework
identities. This ticket does not invent legal control content. Satisfying a
control is not legal certification. Source references preserve provenance but
do not copy regulatory text into compliance tables.

Revisit if framework volume or migration cost creates a measured operational
problem, or if a future requirement needs a different historical model.
