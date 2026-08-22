# EX-006 — Regulatory assessment input stability

Ticket: SCRUM-189  
Research question: RQ-007

## Candidates

- V0: mutable/unconfirmed project context (research-only comparator).
- V1: one immutable snapshot containing only confirmed effective facts (production candidate).

The benchmark contains 12 synthetic scenarios, split before evaluation into 8 development and 4 holdout cases. Retrieval, evidence, provider, prompt and verifier are not varied; the comparison isolates input context.

Hypotheses frozen before execution:

- H1: V1 reduces changes caused only by pending, rejected or irrelevant edits.
- H2: relevant confirmed changes still produce a material assessment change and a new version.
- H3: V1 reduces unsupported claims attributable to unconfirmed context.

The experiment is a deterministic context-integrity comparison, not a claim of legal correctness.
