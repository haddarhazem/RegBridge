# EX-011 — Contract evidence resolution and semantic verification

## Purpose

EX-011 continues RQ-011 after EX-010 exposed two limitations: Mistral-generated
character offsets were unreliable, and exact provenance did not establish
semantic support. EX-010 remains unchanged and V2 remains the extraction
baseline.

## Candidates

- **V2-A:** structured extraction requesting a verbatim quote, followed by
  deterministic exact quote resolution and provenance checks.
- **V2-B:** V2-A followed by a bounded structured semantic verifier receiving
  only the statement, type, category, exact quote, and document-version
  metadata.

The generator and verifier used the same configured Mistral model. This means
their errors may be correlated and the experiment does not establish that a
different model would perform similarly or better.

## Frozen benchmark and execution

`benchmarks/contract_verification_ex011_v1.json` contains 12 development, 8
holdout, and 8 adversarial synthetic cases. Expectations were frozen before
execution. The first execution exposed an implementation defect: the model
returned unbounded reason-code strings and the verifier prompt did not state
the semantic rejection rules strongly enough. The bounded schema and prompt
were corrected using development observations, then the complete benchmark
was rerun as attempt 2. The raw artifact records that rerun.

Only synthetic contracts were sent to the configured production Mistral
provider. No prompts or credentials are stored in the artifact.

## Resolver invariant

The resolver returns `INVALID` for no exact match, `AMBIGUOUS` for multiple
exact matches, and derives offsets only for one exact match. It enforces:

`document_text[start_char:end_char] == quote`

## Mutation coverage

The evaluator/benchmark covers negation, unrelated evidence, fabricated or
overstated claims, recommendation-as-fact, conflict handling, quote changes,
wrong versions, and prompt-injection content. Production changes were not
made as part of this research experiment.

## Limitations

The benchmark is synthetic and small. The same-model verifier can accept
semantically unsupported claims, particularly under adversarial wording.
The result is not evidence that an LLM verifier is safe enough by itself.
