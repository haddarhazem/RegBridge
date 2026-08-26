# EX-024-R2 — Extractive grounding follow-up

## Hypothesis

H-024-R2: constraining factual extraction to exact source segments, rather than allowing the model to generate factual values, should reduce unsupported claims and eliminate numeric/text mutation while preserving useful recall.

## Frozen holdout

`benchmarks/research_extraction_ex024_r2_holdout_v1.json` contains 12 fresh controlled excerpts and 96 field annotations across domains, technologies, research problem, methodology, results, applications, keywords and limitations. Each field has supported and absent examples; exact per-field counts are recorded before execution. The text does not duplicate the original EX-024 development wording.

## Candidates

V0, V1, V2 and V3 are frozen R1 comparators. V4 is extractive evidence-locked selection: the model returns only field status and allowlisted segment IDs; the backend copies exact segment text and builds the abstract deterministically. V4 never accepts a model factual `value`.

## Gates frozen before provider execution

Privacy violations, critical unsupported claims, accepted numeric mutations, negation reversals, wrong-version/invalid evidence, unsupported abstract claims: all zero. Utility floors: recall >= 0.70, usable structured output >= 0.90, evidence provenance >= 0.95, V4 exact-copy integrity = 1.00, V4 abstract factual provenance = 1.00, and explicit-application accuracy >= 0.90.

## Artifact policy

Results are append-only under `artifacts/experiments/ex024/r2/<run_id>/`. A completed run ID cannot be written twice. Raw provider output is stored only in the ignored local artifact directory; tracked summaries contain no private source text or secrets.
