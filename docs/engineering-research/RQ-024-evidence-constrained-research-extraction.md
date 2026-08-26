# RQ-024 — Evidence-constrained research extraction

## Question

Which extraction strategy best reduces unsupported scientific claims while preserving useful discovery completeness?

## Hypothesis

Adding structure and evidence constraints should reduce unsupported claims. A separate verifier may further improve precision, but may increase latency, token cost, and false rejection.

The experiment does not assume that V3 will win.

## Frozen experiment

- Experiment: EX-024 — Evidence-constrained research extraction benchmark
- Benchmark: `benchmarks/research_extraction_ex024_v1.json`
- Decision record: RD-019 (created only after execution)
- Candidates: V0 loose extraction, V1 strict structured extraction, V2 structured extraction with mandatory evidence mapping, V3 V2 plus a separate claim verifier.
- Corpus: 15 controlled synthetic research excerpts, 105 field instances.
- All supported gold values resolve to paragraph 0 of the exact case source. This locator policy is frozen before candidate execution.

## Safety gate

Candidates are compared first by critical unsupported claims, then unsupported-claim rate/evidence precision, provenance coverage, recall, structured validity, operations, and complexity. A production candidate must have zero critical unsupported claims. If none passes, no production strategy is selected.

False pass means an unsupported claim is returned as supported. False block means a gold-supported claim is missed or marked unavailable. False passes have priority for critical scientific claims.

## Reproducibility limits

The provider/model alias, prompt, schema, temperature, token budget, timeout, and retry policy are recorded in EX-024 results. A moving provider alias and live service behavior may limit exact reruns.
