# EX-014 Results

## Decision

Select V0, `compliance-maturity-unweighted/v1`, for production. It has the
smallest explainable policy, no arbitrary importance weights, exact Decimal
reconstruction, and stable behavior when secondary evidence is added. V1 is
not production-eligible because the benchmark's weights are synthetic and no
versioned, defensible source for real weights exists.

The production indicator means “the percentage of controls included by this
method that are satisfied according to the recorded active-evidence policy.”
It is not legal certification, legal probability, regulator approval, or a
guarantee of compliance. Evidence coverage is exposed separately.

## Results

The runner writes `artifacts/experiments/ex014_compliance_scoring_results.json`
programmatically for every candidate/scenario. Both V0 and V1 are
deterministic and reconstructible. The evaluator covers active/revoked
evidence, N/A denominator exclusion, zero eligible controls, framework and
project isolation, historical snapshots, and method/version identity.

The adversarial mutation suite must reject: revoked evidence counting, N/A in
the denominator, duplicate control contributions, wrong framework version,
invalid weights, mutation of method version, rewriting old framework results,
and cross-project evidence. No weighted candidate is selected for production.

## Limitations and revisit conditions

The benchmark uses synthetic controls and does not establish legal importance.
V1 may be revisited only after a documented, versioned internal methodology or
authoritative framework metadata supplies defensible weights. A new formula or
evidence policy requires a new method version; old calculations remain intact.
