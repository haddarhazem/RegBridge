# RD-012 — Visibility-aware startup search

Select V0 pre-filtered authorized search for RQ-017. The requester identity,
public visibility, and active exact profile-revision grant determine the
searchable dataset before any structured filter, ordering, count, offset, or
limit is applied. Public profile fields are always limited to `PUBLIC`;
`INVESTOR_SHARED` profile fields require a matching active grant. Private
fields never enter the search projection.

Search supports only the actual startup fields: sector, stage (`current_progress`),
geography (`location`), and technology. Unknown filters and private-only data
are rejected or treated as absent. Stable ordering uses an allowlisted field
plus project ID. Revocation is observed on the next query; no cache is used.
