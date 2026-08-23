# EX-017 — Visibility-aware startup search

EX-017 compares V0 query-time authorization with V1 broad search followed by
post-filtering. The frozen benchmark contains 12 core scenarios and 10
adversarial scenarios covering private rows, counts, pagination, sorting,
filters, grants, revocation, recipient isolation, and IDOR.

V0 constructs the authorized dataset first, then applies allowlisted filters,
stable ordering, count, offset, and limit. V1 is rejected because even if its
final response removes private rows, private rows can influence totals, pages,
ordering, and filter outcomes.
