# EX-009 - Startup profile visibility

Ticket: SCRUM-192  
Research question: RQ-010

## Candidates

- V0: field-level visibility. Each structured profile field carries exactly
  one of `PUBLIC`, `INVESTOR_SHARED` or `PRIVATE`.
- V1: section-level visibility. Fields are grouped into typed sections and one
  visibility classification applies to the section. The evaluated policy keeps
  a section public when it contains any public field, exposing the mixed-section
  over-sharing risk described in the ticket.

No LLM, embeddings or Qdrant were used.

## Frozen benchmarks and invariants

- Core benchmark: `benchmarks/startup_profile_visibility_ex009_v1.json` (12 cases)
- Adversarial benchmark: `benchmarks/startup_profile_visibility_ex009_adversarial_v1.json` (8 cases)
- Raw results: `artifacts/experiments/ex009_startup_profile_visibility_results.json`

The benchmark files were frozen before candidate execution and contain
candidate-neutral expected projections, authorization outcomes, history
expectations and lifecycle/project contexts. The evaluator checks public
non-disclosure, exact projection, authorization, partial-update safety,
historical preservation, cross-project isolation and visibility changes.

## Evaluation method

The runner loads both JSON files, applies each operation to each candidate,
records per-scenario observations, and derives all aggregate metrics from those
records. V0 projects only fields classified `PUBLIC`. V1 classifies a mixed
section as public when any member is public, which is a deterministic test of
the section-level candidate's over-sharing trade-off.

## Limitations

This is a synthetic architecture experiment, not a production traffic study.
It does not measure user comprehension, database throughput or future grant
workflow behavior. `INVESTOR_SHARED` is treated as non-public and no SCRUM-197
investor grant system is introduced.
