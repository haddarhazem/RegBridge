# RD-010 — Explicit investor sharing

Select V0 resource-level grants for RQ-015. A grant has one project, one
recipient user, one allowlisted resource type, one exact resource ID, optional
exact immutable version, READ scope, and ACTIVE/REVOKED lifecycle. Sharing is
default-deny and does not create project membership. Public and member access
remain separate authorization paths.

Compliance score sharing returns only the immutable score metadata and safe
explanation; it does not grant access to evidence documents. Document grants
target one exact `DocumentVersion`. Profile grants expose only non-private
fields from the selected immutable revision. Conversations are not shareable.

Revisit if an investor profile model is introduced, if bundle UX becomes a
demonstrated requirement, or if a typed non-polymorphic resource registry is
needed. No expiration or write scope is included.
