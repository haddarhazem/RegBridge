# RD-009 — Compliance maturity scoring

Decision for RQ-013: use deterministic unweighted
`compliance-maturity-unweighted/v1`. Eligible controls are applicable
controls; `NOT_APPLICABLE` is excluded. A control contributes only when it is
`SATISFIED` and has at least one currently `ACTIVE` evidence item. There are
no partial points. Decimal half-up rounding to two decimal places is used.

Persist each calculation as an immutable record with method version,
framework version, timestamp, numerator/denominator, evidence coverage, an
input snapshot, and an explanation breakdown. Overall scores aggregate all
eligible controls from active adopted framework versions. No eligible controls
returns unavailable/null, never 100%.

Weighted scoring is rejected for production because EX-014 only supplied
synthetic weights. Evidence coverage is a separate indicator. Scores are
maturity indicators, not certification, legal probability, approval, or a
compliance guarantee. Revisit if defensible versioned weights or a new
evidence policy is approved.
