# Authorization

## Authentication vs authorization

Authentication answers: who are you? SCRUM-178 provides `AuthenticatedPrincipal`.

Authorization answers: what may you access? SCRUM-179 evaluates the authenticated user, project membership, member role/status, and project visibility.

## Project authorization inputs

- authenticated `AuthenticatedPrincipal`;
- project membership relationship;
- membership role;
- membership status;
- project visibility.

Global roles remain available on the principal where a future policy needs them, but project access is not granted by global role alone.

## Project member roles

| Role | Read | Edit | Manage members |
|---|---:|---:|---:|
| owner | yes | yes | yes, except ownership changes |
| founder | yes | yes | yes for non-owner memberships |
| admin | yes | yes | yes for non-owner memberships |
| member | yes | no project update in this ticket | no |
| viewer | yes | no | no |

Ownership transfer is not implemented. The owner membership is created automatically with a project and cannot be changed or revoked through these endpoints.

## Membership lifecycle

```text
invited → active → revoked
```

Only `active` memberships grant member access. `invited` users must accept their own invitation; `revoked` users are denied on the next request through a direct database lookup.

## Object-level authorization

Every project-scoped endpoint loads the project and evaluates authorization before returning or mutating data. Knowing `/projects/{project_id}` never grants access. Private unauthorized resources use 404 to avoid revealing their existence; authenticated but unauthorized management operations use 403.

Public and authenticated non-members receive only a minimal project summary. Internal project fields are not serialized for them.

## Audit

The following operations create append-only `audit_logs` records:

- project creation;
- member invitation;
- invitation acceptance;
- membership revocation;
- member role change;
- project updates.

Audit metadata contains safe operation context only; tokens and secrets are never recorded.

## Deferred sharing

`project_access_grants` and investor-specific sharing are deferred because the V2.1 definition depends on the later `investor_profiles` schema. They are not implemented in SCRUM-179.
