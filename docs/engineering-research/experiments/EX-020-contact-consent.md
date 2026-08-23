# EX-020 — Contact consent model

## Question

Compare acceptance-level consent (V0) with explicit per-channel consent (V1)
for reciprocal investor/startup contact requests.

## Frozen protocol

The core benchmark contains 12 scenarios and the adversarial benchmark contains
12 mutations. Both are frozen in `benchmarks/`. The evaluator is deterministic;
it does not use an LLM, embeddings, private data, or Qdrant. Production safety
is validated separately by PostgreSQL-backed tests.

## Controlled comparison

V0 authorizes a predefined disclosure set at acceptance. V1 requires the
recipient to select each contact point and stores an immutable value snapshot.
The evaluator checks disclosure state, recipient/project isolation, revocation,
IDOR resistance, duplicate pending behavior, and absence of project/grant side
effects.

## Limitations

The abstract protocol evaluator does not measure latency or human usability.
Those concerns are handled by the production tests and code review. It does not
claim that an account email is shareable; contact points are explicit.
