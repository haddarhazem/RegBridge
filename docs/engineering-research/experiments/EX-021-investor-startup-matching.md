# EX-021 — Investor-startup matching

## RQ-021

Which strategy produces a stable, explainable report from frozen authorized
structured snapshots without allowing an LLM to change deterministic results?

## Candidates and frozen protocol

V0 is the deterministic structured matcher. V1 runs the same matcher and adds
an optional LLM explanation whose input is limited to authorized snapshots and
the immutable deterministic result. The benchmark has 20 candidate-neutral
pairs: 16 development pairs and 4 holdout pairs. The adversarial set has 8
development cases and 4 holdout cases. Dimension outcomes are MATCH, MISMATCH,
or UNKNOWN; UNKNOWN is excluded from the score denominator.

The deterministic evaluator and scoring rules were frozen before candidate
comparison. No embeddings, vector search, fuzzy ranking, or investment advice
are used.

## Provider availability

The local environment has no usable `MISTRAL_API_KEY`/`MISTRAL_MODEL`, so no
real provider result is claimed. Stub architecture tests are clearly separate
from real-provider evidence.
