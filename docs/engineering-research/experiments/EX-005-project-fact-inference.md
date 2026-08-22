# EX-005 — Project fact inference with provenance

## Research question

Which inference strategy extracts regulatory-useful project facts with sufficient precision, provenance quality, and understandable uncertainty?

## Frozen protocol

The frozen benchmark is `benchmarks/project_fact_inference_v1.json`: 24 synthetic non-private project descriptions, split before evaluation into 16 development cases and 8 holdout cases. Expected facts, supporting excerpts, ambiguity, and acceptable omission were annotated independently of both candidates.

- V0: conservative deterministic structured extraction with normalized lexical matching and negation safeguards.
- V1: structured extraction through the existing provider-neutral `LLMProvider` and configured Mistral adapter. The provider received only bounded synthetic descriptions, allowed domains, extraction instructions, and a provenance requirement.
- No direct Mistral SDK call was made by experiment business logic; no embeddings, private data, legal conclusions, coaching, chain-of-thought, or cost estimate were used.

Primary priority: precision > provenance correctness > recall.

## Initial development evaluation — EX-005A

The first V1 attempt exposed a structured-output contract mismatch: JSON was syntactically valid but used unsupported keys, yielding 6.25% structured validity. The result was preserved as `ex005a_initial.json`. The smallest correction was to send the explicit JSON schema through the existing provider adapter. No candidate logic or benchmark labels were tuned.

Development metrics after that correction are recorded in the results document. V0 also received only development-justified corrections for explicit negation and unresolved wording such as “à préciser”; the original metrics remain preserved.

## Holdout evaluation — EX-005B

After the correction, implementations were frozen and the untouched eight-case holdout was evaluated. No holdout-driven tuning was performed.
