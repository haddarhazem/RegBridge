# EX-008 results - RQ-009

## Machine-readable artifacts

- Original benchmark: `benchmarks/project_lifecycle_ex008_v1.json` (12 scenarios)
- Adversarial benchmark: `benchmarks/project_lifecycle_ex008_adversarial_v1.json` (10 scenarios)
- Raw results: `artifacts/experiments/ex008_project_lifecycle_results.json`
- Evaluator: `ex008-json-evaluator-v2`

The two benchmark files were frozen before candidate execution. Their expected
invariants are candidate-neutral and aggregate metrics are computed
programmatically from the raw per-scenario results.

## Original EX-008

| Metric | V0 same project | V1 linked project |
|---|---:|---:|
| Scenarios | 12 | 12 |
| Identity continuity | 100% | 100% |
| History preservation | 100% | 100% |
| Authorization correctness | 100% | 100% |
| Reference integrity | 100% | 100% |
| Duplication count | 0 | 7 |
| Audit completeness | 100% | 100% |
| Transition correctness | 100% | 100% |
| Idempotency/concurrency | 100% | 100% |
| Synchronization rules required | 0 | 12 |
| Approximate implementation complexity | 12 | 35 |
| Scenarios passing all frozen invariants | 12 | 7 |

## Adversarial validation

| Metric | V0 same project | V1 linked project |
|---|---:|---:|
| Scenarios | 10 | 10 |
| Identity continuity | 100% | 100% |
| History preservation | 100% | 100% |
| Authorization correctness | 100% | 100% |
| Reference integrity | 100% | 100% |
| Duplication count | 0 | 7 |
| Audit completeness | 100% | 100% |
| Transition correctness | 100% | 100% |
| Idempotency/concurrency | 100% | 100% |
| Synchronization rules required | 0 | 14 |
| Approximate implementation complexity | 10 | 42 |
| Scenarios passing all frozen invariants | 10 | 6 |

The adversarial set includes multiple assessments, partial roadmaps, mixed
visibility documents, revoked membership, all fact states, rollback, retry,
conflicting concurrency, separate roadmap purposes and fragile references.

## Explanation of the historical 91.7% result

The old prototype evaluator reported one failure for each candidate:

- Scenario: `T11`
- Expected behavior: reject the invalid `existing_startup -> idea` transition.
- Old evaluator behavior: counted an invalid transition as incorrect whenever it
  was not accepted, instead of comparing the observed outcome with expected
  validity.
- Classification: evaluator/prototype limitation, not a SCRUM-191 production
  defect.

The JSON-backed evaluator records expected validity explicitly, so the correct
rejection of T11 is now counted as correct. Both candidates score 100% on
transition correctness.

## Mutation and bias validation

The evaluator mutation tests detected each of the following independently:

- dropped assessment reference;
- duplicate membership;
- missing audit record;
- unauthorized access;
- changed historical snapshot.

The evaluator checks frozen, candidate-neutral invariants and reports violated
invariant names in the raw scenario results.

## Decision

Select V0 - the same project aggregate evolves. Use the existing
`projects.project_type` field and an audited, transactional transition service.
Do not create a parallel startup project. Keep creation roadmaps distinct from
future compliance roadmaps using an explicit roadmap purpose.

The result supports V0 on the original and adversarial workloads. This is
strong evidence for the current architecture, but not a universal claim about
future organizational, billing or legal boundaries. Revisit V0 if startup-
specific ownership boundaries, independent billing, legally separate entities,
or an independent authorization boundary are introduced.
