# EX-014 — Deterministic compliance scoring

EX-014 answers RQ-013 by comparing an explainable unweighted candidate (V0)
with a research-only weighted candidate (V1). The benchmark is frozen in
`benchmarks/compliance_scoring_ex014_v1.json` and its adversarial cases in
`benchmarks/compliance_scoring_ex014_adversarial_v1.json`.

Both candidates use the frozen control policy: applicable controls excluding
`NOT_APPLICABLE` are eligible; only `SATISFIED` controls with active evidence
contribute; revoked evidence never contributes; there are no partial points;
zero eligible controls is unavailable. Scores use Decimal half-up rounding to
two decimals. Overall scoring aggregates eligible controls, rather than
averaging framework percentages.

The evaluator is deterministic Python logic and does not use an LLM,
embeddings, Qdrant, or production modules. V1 uses synthetic weights only to
measure behavior around critical synthetic controls. Those weights have no
defensible legal or product-policy source.
