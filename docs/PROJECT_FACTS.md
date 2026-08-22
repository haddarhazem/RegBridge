# Project facts

SCRUM-188 stores conservative, deterministic facts inferred from an idea project's bounded description in `project_facts`.

Inferred facts start as `pending_confirmation` and retain a bounded source excerpt, extraction rule, categorical uncertainty, and `origin: inferred`. Users can confirm, correct, or reject facts through the project-scoped API. Corrections use `status: corrected`, preserve the inferred origin, and retain the original value in provenance metadata. Rejected facts use `status: deleted` and are never included in AI context.

Only active project editors can list or change facts. User-declared onboarding fields remain separate from inferred fact records. The authorized context builder includes only confirmed or corrected facts, preserving the origin/status distinction for downstream agents; pending facts never silently override project context.
