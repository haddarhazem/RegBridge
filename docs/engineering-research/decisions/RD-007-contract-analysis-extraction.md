# RD-007 - Contract analysis extraction strategy

Status: ACCEPTED  
Ticket: SCRUM-193  
Research: EX-010 / EX-011 / EX-012 / RQ-011

## Decision

Use V2 structured extraction, but expose only exact source-linked
observations. The model must provide a verbatim quote; the application derives
canonical offsets with a deterministic resolver against the exact immutable
`DocumentVersion`. Model-generated offsets are not trusted.

EX-011 and EX-012 did not produce a semantic verifier meeting the safety gate.
Therefore model paraphrases, legal conclusions, inferred obligations, risks,
recommendations, and conflict/negation/condition interpretations are withheld
from confirmed output. Empty risk and recommendation lists mean that these
outputs were not safely generated, not that the contract has no risks or
recommendations.

The workflow is source-observation-only and must not modify, replace or
rewrite the source contract. It is not legal certification, automated legal
review equivalent to a lawyer, guaranteed risk detection, or guaranteed
recommendation generation.

## Evidence

On the 8-case holdout, V2 reduced unsupported finding rate to 20% versus
42.86% for both V0 and V1, raised precision to 80%, and achieved 100% exact
span validity. On the 8-case adversarial set, V2 reached 14.29% unsupported
findings, 85.71% precision and 100% span validity. V0 had no reproducible
evidence and V1 had no evidence requirement.

The evaluator mutation suite detected all eight required failure classes.

EX-011 resolved 28/28 verbatim quotes deterministically, but its same-model
verifier retained 42.86% adversarial false support. EX-012 found no eligible
verifier: V0 had 62.5% holdout false support and V1 had 62.5%; neither met the
5% holdout / 10% adversarial gate. No semantic verifier is deployed.

## Production constraints

- Every analysis references one exact document and document version.
- Source versions are immutable; a revised upload creates a new version.
- Public API observations contain only exact source excerpts; confirmed risks
  and recommendations are unavailable and explicitly documented as withheld.
- Evidence quotes and offsets are derived deterministically against the
  persisted canonical text; duplicate matches are rejected as ambiguous.
- Project/document authorization is rechecked for analyze, read and history.
- Provider failures and malformed structured output produce a safe failed state.
- Traces contain bounded IDs/metadata only, never full private contract text,
  prompts, secrets or authorization headers.

## Revisit conditions

Semantic risk/recommendation generation may be reconsidered only under a later
explicitly scoped research ticket when a verifier strategy demonstrates
acceptable false-support performance on an independently frozen benchmark.
