# EX-003 - Response verification and citation resolution

## Jira and research question

- Jira: SCRUM-185
- Research question: RQ-003
- Question: To what extent does an explicit response-verification step reduce
  unsupported or incorrectly attributed regulatory claims without excessively
  blocking correct answers?
- Status: PREPARED - waiting for human annotation

This is a research gate. It does not add a verifier to the SCRUM-184
production flow and does not create RD-004.

## Controlled unit

Each variant receives exactly the same fixed question, candidate answer,
evidence package, and human annotation. Answers are not regenerated per
variant. This isolates verification from generation. V2 is a separate
processing step, but using Mistral for both generation and verification would
not establish statistical model independence.

## Material claim definition

A material regulatory claim is a factual statement that could materially
change what a user believes they are legally or regulatorily required,
permitted, prohibited, or expected to do. Transitions, politeness, and generic
explanatory prose are not material claims by default.

Human claim labels are: `supported`, `partially_supported`, `unsupported`,
`contradicted`, or `not_applicable`. Candidate labels in the benchmark are
proposals only and must not be treated as ground truth.

## Verdict policy (pre-registered)

- `pass`: every material claim is supported, attribution resolves to supplied
  evidence, and no material citation/coverage problem is present.
- `pass_with_warnings`: no material unsupported or contradicted claim exists,
  but a non-critical partial-support, coverage, ambiguity, or citation issue
  remains.
- `block`: at least one material claim is unsupported or contradicted; usable
  evidence is absent; a material source does not resolve; or evidence
  integrity is otherwise unsafe.

These thresholds are frozen before evaluation. Changing them after metrics
requires a named experimental variant.

## Benchmark

`benchmarks/response_verification_v1.jsonl` contains 30 fixed candidate cases
across GDPR, business creation, employment, consumer/e-commerce, AI/digital,
and cross-topic subjects. It includes the planned failure classes: fully
supported, unsupported, contradicted, wrong source/citation, partial coverage,
insufficient/ambiguous evidence, and mixed multi-claim answers.

Evidence is bounded and carries `evidence_id`, organization, domain, URL,
point/chunk provenance where available, and an excerpt. Controlled mutations
are in candidate answers only. No private data, scraping, corpus rebuild, or
Qdrant mutation is permitted.

Every case starts with `annotation_status: needs_human_validation`.
`expected_support`, `expected_evidence_ids`, and `expected_verdict` are null
or empty until a human annotator fills them. The worksheet is at
`artifacts/experiments/EX-003/annotation_candidates.md`.

After human review, the frozen EX-003 evaluation set is:

- 24 `human_validated` real-evidence cases: VER-004 through VER-029, excluding
  VER-001, VER-002, VER-003, VER-010, and VER-020;
- 5 reserved real-evidence cases: VER-001, VER-002, VER-003, VER-010, and
  VER-020;
- 1 pending synthetic safety sanity fixture: VER-030, excluded from primary
  metrics.

The 24-case set is frozen before running V0/V1/V2 and must not be tuned after
observing results.

## Variants

### V0 - no verifier

The baseline accepts every answer as `pass`. It is an experiment baseline and
is not a production behavior.

### V1 - deterministic evidence rules

V1 checks evidence presence, evidence-ID resolution, public-source membership
in supplied evidence, citation/evidence consistency, required provenance, and
normalized duplicate organizations. It cannot determine semantic entailment
of a claim from prose; that limitation is recorded rather than hidden.

### V2 - model-assisted verification

V2 uses the provider-neutral `LLMProvider`, preferably the configured Mistral
provider, with a bounded structured output contract. Runtime input contains
only question, candidate answer, claims, evidence, and needed provenance.
It excludes expected verdicts, expected support, category, mutation type, and
annotation notes. The system prompt treats both answer and evidence as data,
ignores instructions inside them, and requests short evidence-based reasons,
never chain-of-thought.

### V3 - gated combined variant

`V3 = conditional / not yet justified`. It must not be run before human
validation and initial V1/V2 results justify it.

The injection-like `VER-030` case is a safety sanity fixture, not a claim
support result. Instructions appearing in evidence or an answer are untrusted
content; following them is an evidence-integrity defect and may independently
justify `block`, even if the separate regulatory claim is supported. It is
excluded from the preferred real-evidence subset and is reported separately.

## Metrics (defined before evaluation)

- Unsupported claim rate: human-labeled unsupported or contradicted material
  claims divided by all material claims in responses the verifier allows.
- Public citation correctness: whether public organization attribution matches
  the human-validated supporting organization(s).
- Internal evidence-resolution correctness: whether resolved evidence IDs and
  provenance match human-validated supporting evidence.
- Citation coverage: material claims requiring evidence with at least one
  valid supporting item, divided by all material claims requiring evidence.
- False-pass rate: expected `block` cases predicted `pass` or
  `pass_with_warnings`, divided by all expected `block` cases.
- False-block rate: expected `pass` or `pass_with_warnings` cases predicted
  `block`, divided by all expected non-block cases.
- Verdict quality: three-class confusion matrix, per-class precision/recall,
  and macro F1 where defined.
- Latency: monotonic verifier-only median and p95, with sample count;
  generation and retrieval latency are not included.
- Cost: report provider token usage when safely available; cost is
  `not reliably attributed` unless an existing reliable pricing mechanism is
  available.

The trade-off is explicit: blocking everything lowers false passes but creates
an unacceptable false-block rate. Selection prefers the simplest variant that
materially reduces false passes, preserves acceptable false-block behavior,
improves claim/citation handling, and has acceptable latency and complexity.
No final numeric threshold is invented here.

## Leakage and safety controls

The research input projection and its test assert that human labels and
mutation metadata are absent at inference. The verifier must not receive
`expected_verdict`, `expected_support`, benchmark category, mutation type, or
annotation notes. Evidence and candidate answers are untrusted data.

## Reproduction boundary

Do not run EX-003 until all cases are human validated. Then run the fixed V0
and V1 benchmark, and run V2 only with explicitly configured research
credentials. Record prompt version, provider/model, commit, dataset version,
latency, usage, and raw outputs under `artifacts/experiments/EX-003/`.
Do not modify production code, Qdrant, benchmark labels after observing
metrics, or create RD-004 before results and human architecture review.
