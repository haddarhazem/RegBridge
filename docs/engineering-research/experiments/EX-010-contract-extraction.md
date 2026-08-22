# EX-010 - Contract extraction strategy

Ticket: SCRUM-193  
Research question: RQ-011  
Taxonomy: `contract-taxonomy-v1`

## Hypotheses frozen before execution

- H1: structured extraction improves schema and classification consistency over
  direct prompting;
- H2: mandatory evidence reduces unsupported findings;
- H3: evidence requirements may reduce recall when evidence is insufficient;
- H4: V2 should improve unsupported-finding safety and explainability only if
  the measured benefit justifies the additional output constraint.

## Candidates

- V0: direct prompting with no strict response schema or evidence requirement;
- V1: structured extraction with explicit finding types and categories;
- V2: V1 plus immutable document-version evidence, quote and character offsets.

The same deterministic synthetic rule harness, taxonomy and temperature were
used for all three candidates. No private contracts, LLM calls, embeddings or
provider-cost claims were used in this experiment. The harness isolates output
strategy; provider performance remains a limitation for a later provider
validation.

## Frozen corpus

- Development: 12 cases in `benchmarks/contract_extraction_ex010_v1.json`;
- Holdout: 8 untouched cases in the same file;
- Adversarial: 8 cases in `benchmarks/contract_extraction_ex010_adversarial_v1.json`;
- Raw results: `artifacts/experiments/ex010_contract_extraction_results.json`.

All text is canonical UTF-8 synthetic contract text. Evidence offsets use
start-inclusive/end-exclusive indexes into the exact persisted text.

## Evaluation

The evaluator matches generated findings to manually authored expected finding
IDs by category, checks type/category correctness, forbidden categories,
structured validity and exact evidence spans, and derives aggregate metrics
from raw per-case/per-finding records. Holdout and adversarial results remain
separate.

## Error analysis

- V0 frequently merged uncertainty/recommendation semantics into FINDING and
  produced no reproducible evidence.
- V1 fixed schema/type representation but had the same unsupported detections
  for negation and conflicting clauses because it lacked evidence gating.
- V2 suppressed explicit negations and produced valid spans, but conflicting
  clauses in D05/H08/A03 still caused duplicate or overly narrow matching.
  These remain unsupported or partially matched rather than being treated as
  certain legal conclusions.
- The injection case A06 did not convert document text into an instruction.

## Separate verifier decision

No separate LLM verifier is selected. Deterministic schema validation,
document-version checks and exact quote/offset validation are sufficient for
the measured V2 gate in this ticket. Residual unsupported findings are
blocked or marked uncertain by the production evidence gate. A separate
verifier would require its own controlled experiment.

## Limitations

The rule harness is not a legal correctness judge and does not establish model
quality for arbitrary contracts, languages or providers. Token usage and cost
were unavailable and are intentionally recorded as null. A later experiment
may validate V2 with the configured provider on an authorized corpus.
