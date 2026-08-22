# EX-013 results — Compliance control model

## Results

| Candidate / split | Pass rate | Historical reproducibility | Framework-version integrity | Evidence revocation | Project isolation | Framework isolation | Upgrade correctness |
|---|---:|---:|---:|---:|---:|---:|---:|
| V0 materialized / core | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| V0 materialized / adversarial | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| V1 dynamic / core | 75% | 83.33% | 100% | 91.67% | 100% | 100% | 91.67% |
| V1 dynamic / adversarial | 50% | 75% | 87.5% | 87.5% | 87.5% | 87.5% | 75% |

V0 materialized 9 duplicated control records across the core scenarios and 3
across adversarial scenarios. V1 had zero duplicated materialized control
records, but required fewer explicit state rules while failing historical and
revocation invariants in the dynamic cases.

## Decision

Select **V0 materialized project controls**. It preserves exact framework
version identity, historical reproducibility, explicit adoption/upgrades, and
evidence history. V1 is rejected because current framework definitions can
change historical views and its dynamic evidence correlation can retain
revoked evidence.

No hybrid is required by the measured scenarios. The selected production
model should use separate reference-data tables for frameworks, versions and
control definitions, and project-owned materialized controls for state.

Evidence strength: **MODERATE**. The result is deterministic and covers the
required invariants, but the benchmark uses synthetic domain data.

## Production implications

- GDPR/RGPD and EU AI Act are supported as independent framework identities;
  no legal obligations are fabricated by this ticket.
- Framework versions become immutable once active/published.
- A project remains on its adopted version until an explicit audited upgrade.
- Evidence is project-owned, supports immutable `DocumentVersion` references
  or bounded structured declarations, and has ACTIVE/REVOKED lifecycle.
- Revoked evidence is excluded from current counts but retained for history.
- Source references remain metadata/provenance links and are not copied into
  control tables.
- Future frameworks require data, not framework-specific schema tables.
