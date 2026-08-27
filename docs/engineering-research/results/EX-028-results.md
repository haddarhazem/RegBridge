# EX-028 — Minimum Observability Comparison

## Protocol

The same frozen synthetic scenarios were evaluated for O0 and O1. Business
behavior and failure inputs were held constant. No production systems,
credentials, private documents, Qdrant writes or paid monitoring services were
used. Raw output is in `artifacts/experiments/EX-028/results.json`.

## Results

| Candidate | Detection | Localization | Correlation | Private leakage | Secret leakage | Non-actionable alerts | Median signal events |
|---|---:|---:|---:|---:|---:|---:|---:|
| O0 | 100% | 100% | 100% | 0 | 0 | 0 | 3 |
| O1 | 100% | 100% | 100% | 0 | 0 | 0 | 4 |

F1–F8 were detected and localized. F9 is `NOT_APPLICABLE`: no worker exists
in the current architecture. All applicable scenarios retained request
correlation; GenAI partial failure retained the child run identifier and
existing parent/run lineage. Sentinel leakage was zero.

## Decision

O0 satisfies every pre-registered hard gate. O1 provides no measured gate
improvement and adds signal overhead, so the simplest strategy is selected.

`RQ-028` is decision-grade. See `RD-024-minimum-observability.md`.
