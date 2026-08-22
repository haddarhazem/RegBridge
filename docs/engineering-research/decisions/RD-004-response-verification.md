# RD-004 — Response verification baseline

## Decision

Select the V3 structural + semantic cascade as the current production
baseline for SCRUM-185.

```text
if structural verdict == block:
    final = block
else:
    final = semantic verdict
```

## Responsibilities

The deterministic structural verifier checks that evidence and citation
references resolve, provenance exists, public organization attribution matches
the supplied evidence, and required evidence metadata is present. A material
integrity failure blocks without calling the semantic verifier.

The semantic verifier uses the provider-neutral `LLMProvider` to assess
material claims against supplied evidence. It returns `pass`,
`pass_with_warnings`, or `block`, with short evidence-based reasons and no
chain-of-thought.

If semantic verification is required but unavailable or invalid, the result
is externally non-reliable/block and the technical failure category is kept
internally. It is never silently converted to `pass`.

## Scope and limitations

The evidence is based on 24 human-validated real-evidence cases and 5 reserve
cases. V3 was proposed after observing V1/V2 complementarity on the same
24-case benchmark, so its measured performance is exploratory and not a
universal guarantee. The experiment evaluates grounding against supplied
evidence, not universal legal truth. Provider behavior may change, and the
measured latency and token savings are benchmark-specific.

## Status

**ACCEPTED CURRENT BASELINE FOR SCRUM-185 IMPLEMENTATION**
