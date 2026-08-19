# EX-001 - Custom orchestrator vs framework

## Related Jira

SCRUM-183

## Related Research Question

RQ-001

## Status

PLANNED

## Goal

Compare a lightweight Python/Pydantic orchestrator with one credible framework
candidate. Do not select the framework winner in advance.

## Fixed test workflow

intent classification -> routing -> authorized ContextBuilder ->
controlled/fake agents -> structured output -> trace

## Evaluation criteria

- testability
- authorization control
- traceability
- partial failure handling
- debuggability
- provider independence
- extensibility
- implementation complexity
- dependency footprint
- runtime overhead, if meaningful

## Qualitative scoring rubric

Use a 1-5 scale: 1 = poor, 2 = weak, 3 = acceptable, 4 = strong,
5 = excellent.

| Criterion | Weight |
| --- | ---: |
| Authorization control | 5 |
| Testability | 5 |
| Traceability | 5 |
| Debuggability | 4 |
| Extensibility | 4 |
| Failure handling | 4 |
| Provider independence | 3 |
| Implementation complexity | 3 |
| Dependency footprint | 2 |
| Runtime overhead | 1 |

The weighted score is decision support, not scientific truth. Qualitative
evidence and limitations must still be discussed.

This directory is preparation only. The orchestrators and experiment runner
will be implemented under SCRUM-183.
