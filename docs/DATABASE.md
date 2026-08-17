# Database

## Technology

- PostgreSQL 15
- SQLAlchemy 2.x async
- asyncpg
- Alembic

## Foundation tables

The authoritative source is `docs/specs/RegBridge_DATABASE_SCHEMA_V2.1_RESEARCH.md`. This ticket implements only the explicitly approved subset below.

SCRUM-177 implements only the V2.1 foundation subset:

- `users`: application users; authentication credentials remain with the OIDC provider.
- `user_identities`: external provider and subject mapping to `users`, unique per provider and subject.
- `roles`: global role reference data.
- `user_roles`: unique many-to-many assignment between users and global roles.
- `projects`: idea, startup-in-creation, and existing-startup records owned by a user.
- `project_members`: project membership and member role, unique per project/user pair.
- `audit_logs`: append-only sensitive-action foundation with optional actor and project references.

Essential foreign keys, check constraints, uniqueness rules, and indexes are defined in the Alembic revision. Global role seed data is intentionally separate from schema migration and is not included in SCRUM-177.

`user_consents` is deferred. `project_access_grants` is also deferred because V2.1 references `investor_profiles`, which belongs to a later investment increment. No investment-domain tables are included here.

## Migration policy

Model/schema change → Alembic migration → review → test on a disposable database → upgrade. Alembic is the source of truth; the application does not call `Base.metadata.create_all()`.

## Rollback / roll-forward strategy

Development migrations may be downgraded on disposable databases when safe:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://regbridge:regbridge@localhost:5432/regbridge"
alembic upgrade head
alembic current
alembic downgrade -1
alembic upgrade head
```

Once a migration is applied to a shared environment, do not edit its history. Prefer a new roll-forward migration. Future destructive changes should add new structure, backfill, switch application behavior, and remove old structure only in a later migration.
