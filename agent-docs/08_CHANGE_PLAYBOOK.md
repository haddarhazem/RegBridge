# Change Playbook

Use this guide to find the smallest safe change surface.

## Before editing

```powershell
git status --short
rg --files app frontend tests docs
```

Then:

1. Read the Jira ticket and research gate.
2. Inspect existing implementation and tests.
3. Identify authorization and version/snapshot boundaries.
4. Preserve unrelated dirty-tree changes.
5. Define focused validation.

## Where to change what

### Add or modify an API use case

1. Pydantic request/response contract in the owning module.
2. Service method with state and authorization rules.
3. Repository query if persistence changes.
4. Thin router endpoint.
5. Positive, validation, unauthorized, cross-object, and revoked-access tests.

Avoid adding SQL or business logic to the router.

### Add a database field/table

1. Confirm it exists in the approved database specification or update that decision under the current ticket.
2. Edit the owning SQLAlchemy model.
3. Add a focused Alembic migration.
4. Update contracts/repository/service deliberately.
5. Validate clean upgrade and `alembic check`.

### Add a project-scoped capability

Reuse project authorization. Test at minimum:

- active authorized member succeeds;
- unauthenticated caller fails;
- non-member fails without disclosure;
- revoked member fails immediately;
- caller knowing the object UUID still fails;
- audit event exists for sensitive changes.

### Add document processing/analysis

- Require exact clean `document_version_id`.
- Keep bytes in object storage.
- Persist job/run state and bounded retry behavior.
- Do not overwrite a version.
- Keep provider failure terminal and safe.
- Add content, authorization, quarantine, and provenance tests.

### Add an AI agent/tool

- Check the Jira experiment gate first.
- Use ContextBuilder and typed DTOs.
- Use the existing `LLMProvider` abstraction.
- Keep deterministic fields authoritative.
- Add evidence/semantic validators and fallback.
- Persist allowlisted trace projections.
- Do not add an orchestration framework or import experiment code.

### Add a frontend view

- Reuse the relevant `frontend/<workspace>/` app/router/store/view conventions.
- Reuse design tokens and shared auth/API helpers.
- Implement loading, empty, partial, success, error, and unauthorized states.
- Keep URL query parameters as navigation state, not authorization.
- Add source tests and browser coverage where available.
- Check responsive layout, keyboard use, reduced motion, and overflow.

### Add an investor/research sharing feature

- Reuse explicit visibility and grant services.
- Bind access to the exact resource/snapshot/version.
- Fail closed when a grant is missing, expired, or revoked.
- Avoid promoting a grant into project membership.
- Audit consent/permission changes.

## Research-first workflow

When Jira defines an experiment gate:

```text
question/hypothesis
-> frozen dataset and acceptance metrics
-> controlled experiment under experiments/
-> recorded result including failures
-> research decision/ADR
-> selected production implementation
```

Do not write a preferred conclusion before running the experiment. Keep provider/model/retrieval variables stable unless the experiment explicitly compares them. Production must not import the experiment implementation.

## Validation matrix

| Change | Minimum validation |
| --- | --- |
| Documentation only | link/path check, secret scan, `git diff --check` |
| Frontend style/layout | focused source tests, JS syntax, responsive browser check |
| Frontend behavior | source/component tests, API-mocked tests, browser flow |
| Service/policy | focused pytest plus negative authorization tests |
| API contract | service tests plus HTTP integration tests |
| Model/migration | focused tests, clean `alembic upgrade head`, `alembic check` |
| AI/provider | deterministic tests, malformed/failure/fallback tests; live only if authorized |
| Shared auth/security | focused security tests plus full regression |

## Commit discipline

- Do not commit or push unless requested.
- Keep commits organized by coherent functionality when asked for separate commits.
- Do not include local `.env`, credentials, generated benchmark artifacts, browser recordings, or unrelated dirty changes.
- Before a commit, inspect `git diff --cached` and run `git diff --check`.

## Completion report

Tell the user:

- outcome first;
- files changed;
- important behavior/constraints;
- validation commands and results;
- assumptions and genuine unresolved issues;
- whether a commit/push occurred.

Stop at the Jira ticket boundary. Do not use completion as permission for adjacent redesigns or external mutations.

