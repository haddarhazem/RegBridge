# EX-006 results — RQ-007

The synthetic benchmark was evaluated once with the frozen 8/4 development/holdout split. No production retrieval, provider or verifier was changed and no private data was used.

| Variant | Equivalent-input stability | Correct sensitivity | Unsupported-claim rate | Source correctness | Category correctness | Snapshot traceability |
|---|---:|---:|---:|---:|---:|---:|
| V0 mutable/unconfirmed | 33.3% | 100.0% | 41.7% | 100.0% | 100.0% | 100.0% |
| V1 confirmed snapshot | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | 100.0% |

V0 changed on pending or deleted facts that were expected to remain stable. V1 remained stable for those cases while still changing for relevant confirmed changes. The result supports V1 as the production input strategy. It does not establish legal correctness; official evidence grounding and SCRUM-185 verification remain required.

## Decision

Select the immutable confirmed snapshot strategy for SCRUM-189 production. Keep V0 research-only.
