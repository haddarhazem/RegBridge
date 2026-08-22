# EX-007 results — RQ-008

EX-007 was run once on the frozen 16-case benchmark. V0 and V1 used the same assessment fixtures; only the roadmap-generation strategy differed.

| Variant | Supported-step rate | Unsupported-step rate | Type correctness | Traceability | Ordering correctness | Required-action recall | Structured validity |
|---|---:|---:|---:|---:|---:|---:|---:|
| V0 direct | 87.9% | 12.1% | 37.9% | 87.9% | 100.0% | 100.0% | 100.0% |
| V1 constrained typed | 100.0% | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

V0 misclassified recommendations and uncertainties as obligations and added unsupported mandatory actions in cases with explicit negative constraints. V1 preserved the assessment type, linked each item to its conclusion ID, and did not invent generic steps. The result supports V1 for production.

## Decision

Select V1 constrained typed roadmap generation. Keep V0 research-only. Ordering is preserved only where the assessment supplies an order; EX-007 does not establish universal legal sequencing.
