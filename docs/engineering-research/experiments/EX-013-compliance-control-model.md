# EX-013 — Compliance control model

## Research question

RQ-012 asks which persistence model represents versioned compliance
frameworks, project controls, evidence, and historical state reproducibly and
extensibly.

## Frozen invariants

The experiment froze framework-version identity, historical reproducibility,
no silent framework mutation, evidence revocation safety, historical evidence
preservation, source integrity, project/framework isolation, extensibility,
applicability preservation, explicit upgrades, and authorization.

## Candidates

- **V0 — materialized project controls:** adopting a framework version creates
  project-owned control instances bound to exact control definitions and the
  adopted framework version.
- **V1 — dynamic project controls:** current controls are derived from the
  framework definition at read time rather than materialized for the project.

The benchmark is deterministic and uses synthetic framework/control metadata;
it does not invent GDPR or AI Act legal obligations.

## Benchmark

`benchmarks/compliance_control_model_ex013_v1.json` contains 12 core
scenarios. `benchmarks/compliance_control_model_ex013_adversarial_v1.json`
contains 8 adversarial scenarios. Both were frozen before execution and loaded
directly by the runner. No LLM, Mistral, embeddings, Qdrant, or framework was
used.

## Evaluator

The evaluator has mutation tests for revoked evidence, wrong framework
versions, historical rewrites, cross-project evidence, source provenance
loss, framework contamination, and silent upgrades. Expectations are read
from the frozen JSON and are not inferred by a candidate.

## Limitations

This is a deterministic architecture experiment, not a legal-content
validation. Control definitions are synthetic, and production authorization
and concurrency require PostgreSQL-backed tests after implementation.
