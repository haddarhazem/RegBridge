# RD-006 - Startup profile visibility strategy

Status: ACCEPTED  
Ticket: SCRUM-192  
Research: EX-009 / RQ-010

## Decision

Use field-level visibility for structured startup profile attributes. Each
profile field has an explicit validated classification:

- `PUBLIC`: eligible for the public profile projection;
- `INVESTOR_SHARED`: non-public and reserved for a future explicit investor
  grant workflow;
- `PRIVATE`: visible only through authorized startup-member access.

Reuse the SCRUM-191 project identity. Do not create a second startup aggregate
or anticipate SCRUM-197 grants.

## Evidence

EX-009 evaluated 12 core and 8 adversarial JSON-backed scenarios. V0 passed
20/20 with zero private or investor-shared public exposure, 100% visibility
classification correctness, 100% projection precision/recall and zero
duplication. V1 passed 16/20 but exposed hidden values in mixed sections, with
25% core and 22.22% adversarial private/unauthorized exposure rates. The
privacy gate therefore rejects V1 despite its lower metadata count.

The evaluator mutation suite detected private leaks, investor-shared leaks,
dropped public fields, unauthorized edits, historical rewrites and
cross-project leaks.

## Production constraints

- Public serialization must be a dedicated visibility-aware projection, never
  an unrestricted ORM serialization.
- Unknown visibility values fail closed.
- `INVESTOR_SHARED` must never appear in anonymous/public responses and does not
  grant investor access by itself.
- Profile revisions are immutable and retain both value and visibility at the
  time of the revision.
- Updates are field-scoped and authorized through existing active project
  membership rules.

## Revisit conditions

Revisit if SCRUM-197 introduces explicit investor grants, if a profile needs a
separate authorization boundary, or if production evidence shows that field-
level validation cannot support a required structured profile domain.
