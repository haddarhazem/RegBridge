# RD-015 — Explicit contact-channel consent

Status: accepted for SCRUM-202.

Select V1: a recipient explicitly selects shareable contact points when
accepting a request. Persist the exact value snapshot in a consent record;
revocation affects future disclosure and does not grant project membership,
startup visibility, investor sharing grants, document access, or any other
resource permission.

The decision is based on EX-020's 24-case deterministic protocol: V0 and V1
had zero unauthorized disclosures, while V1 has safer future-channel and
partial-revocation semantics. Account email is not implicitly shareable.

Abuse moderation beyond self-request, authorization, duplicate-pending, and
scope checks remains deferred because no existing block model was found.
