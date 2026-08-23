# RD-014 — Minimal event participation consistency

Select V0 for RQ-019: one mutable current participation row per
`(event_id, user_id)` with an explicit participation state and an atomic audit
transition. Interest and registration are explicit API actions; registration
supersedes an existing interest for the same user/event. Withdrawal is
idempotent and does not delete the audit history. A database uniqueness
constraint and row lock/upsert handling prevent duplicate active state under
concurrency.

Cancellation is a dedicated organizer action. It preserves the event and all
participation history but blocks new interest or registration. Participation
does not grant project, startup, investor, or private-resource access.

Evidence is moderate: the deterministic benchmark shows V0 satisfies the
frozen invariants with fewer synchronization rules and writes than V1. Revisit
if append-only legal/audit requirements, moderation workflows, invitations,
attendance, or richer participation transitions become product requirements.
