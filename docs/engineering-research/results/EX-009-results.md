# EX-009 results - RQ-010

## Artifacts

- Core benchmark: `benchmarks/startup_profile_visibility_ex009_v1.json` (12 scenarios)
- Adversarial benchmark: `benchmarks/startup_profile_visibility_ex009_adversarial_v1.json` (8 scenarios)
- Raw results: `artifacts/experiments/ex009_startup_profile_visibility_results.json`
- Evaluator: `ex009-json-evaluator-v1`

All metrics below are generated from the raw per-scenario JSON results.

## V0 - Field-level visibility

| Metric | Core | Adversarial |
|---|---:|---:|
| Scenarios passed | 12/12 | 8/8 |
| Private/unauthorized exposure rate | 0% | 0% |
| Private exposure rate | 0% | 0% |
| Investor-shared public exposure rate | 0% | 0% |
| Visibility classification correctness | 100% | 100% |
| Public projection precision | 100% | 100% |
| Public projection recall | 100% | 100% |
| Unauthorized modification rate | 0% | 0% |
| Partial-update integrity | 100% | 100% |
| Historical reproducibility | 100% | 100% |
| Cross-project isolation | 100% | 100% |
| Visibility-change correctness | 100% | 100% |
| Duplication/synchronization burden | 0 | 0 |
| Metadata entries | 27 | 16 |

## V1 - Section-level visibility

| Metric | Core | Adversarial |
|---|---:|---:|
| Scenarios passed | 10/12 | 6/8 |
| Private/unauthorized exposure rate | 25% | 22.22% |
| Private exposure rate | 16.67% | 22.22% |
| Investor-shared public exposure rate | 8.33% | 0% |
| Visibility classification correctness | 83.33% | 75% |
| Public projection precision | 82.35% | 77.78% |
| Public projection recall | 82.35% | 77.78% |
| Unauthorized modification rate | 0% | 0% |
| Partial-update integrity | 100% | 100% |
| Historical reproducibility | 100% | 100% |
| Cross-project isolation | 100% | 100% |
| Visibility-change correctness | 100% | 100% |
| Duplication/synchronization burden | 3 | 2 |
| Metadata entries | 21 | 14 |

V1 exposed hidden values in mixed sections, including the public-to-private
change and mixed semantic-section cases. It is not eligible for production
because privacy/non-disclosure has priority over lower metadata count.

## Evaluator mutation validation

The candidate-independent evaluator detected all required mutations:

- private field exposed publicly;
- investor-shared field exposed publicly;
- public field unexpectedly dropped;
- unauthorized edit accepted;
- historical revision altered;
- cross-project field leaked.

## Decision

Select V0 - field-level visibility. It is the only tested candidate with zero
private/investor-shared exposure and perfect public projection precision/recall
on both benchmark sets. It also preserves mixed-sensitivity sections without
duplicating fields or requiring section synchronization.

Do not build a hybrid: V0 satisfies the frozen invariants without one.

Evidence strength: STRONG for the tested synthetic workload, with the
limitations documented in EX-009.
