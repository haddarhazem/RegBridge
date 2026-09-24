# Contract Analysis V2

RegBridge analyses a clean, immutable document version selected by an active
project member. It never changes the uploaded source and it does not return a
legal-validity, compliance, signability, or legal-advice verdict.

## Ingestion and extraction

PDF, DOCX, and UTF-8 TXT versions first use native extraction. PDF extraction
uses a deterministic quality check: usable native pages remain native; an
image-only or insufficient document requires OCR. For a mixed PDF, RegBridge
keeps usable native pages and replaces only insufficient pages with OCR output
when the provider returns the corresponding page count. The current Mistral
adapter processes one file per request, so mixed-page provenance is retained
even though the provider upload contains the source file once.

OCR is disabled unless `DOCUMENT_EXTERNAL_PROCESSING_ENABLED=true`. It uses
`MISTRAL_API_KEY` and `MISTRAL_OCR_MODEL` through the provider-neutral OCR
adapter. The external file is deleted after processing. Raw pages, provider
payloads, and credentials are never written to agent traces or application
logs. OCR output retains page number, source method (`NATIVE`, `OCR`, or
`MIXED`), and stable extracted-text offsets. OCR-derived passages carry an OCR
limitation in the analysis UI.

## Analysis pipeline

```text
immutable document version
  -> native extraction / bounded OCR fallback
  -> normalized, page-mapped text
  -> document-first section segmentation
  -> semantic section analysis
  -> deterministic evidence verification
  -> semantic cross-section consistency pass
  -> persisted verified findings
  -> risk aggregation, UI, and Contract Agent
```

Section segmentation precedes clause classification. It recognizes actual
article headings, numbered headings, uppercase titles, and paragraph groups
when headings are absent. It does not search the clause taxonomy to invent a
document structure. Unknown sections remain available as `OTHER`.

Semantic analysis is provider-neutral and uses the configured RegBridge LLM
provider only when both `DOCUMENT_EXTERNAL_PROCESSING_ENABLED=true` and
`CONTRACT_EXTERNAL_SEMANTIC_ANALYSIS_ENABLED=true`. Its structured output is a
proposal, not a trusted conclusion. If semantic analysis is disabled or the
provider fails, the persisted result is `partial`: it shows only verified
structure and never presents heuristic risks as final findings.

## Evidence and consistency

Each material semantic finding must include a quoted claim and section ID. The
evidence verifier resolves the quote only in the specified section, first
exactly and then with a bounded whitespace/punctuation-safe match. It rejects
wrong-section, missing, and ambiguous evidence. Unverified findings remain
visible only as review-required material and contribute zero to the risk index.

The consistency pass receives structured section summaries and may report an
inconsistency only with two independently verified evidence excerpts from two
sections. It does not silently bind a duration, payment, or ownership claim to
unrelated document wording.

## Indice de risque contractuel

The **Indice de risque contractuel** is a review-navigation aid. It is not a
legal score or a decision to sign.

Only verified material findings contribute:

- normal `FOUND / low` clauses contribute `0`;
- verified medium, high, and critical issues contribute `2`, `4`, and `6`;
- verified missing expected provisions add `2`;
- verified contradictions add `2`;
- the sum is doubled and capped at `100`.

The response lists every contributor and the formula. Unverified findings add
zero.

## Contract Agent and access control

The Contract Agent reads only a completed, authorized, persisted analysis. It
uses verified findings and the smallest available evidence excerpt; it does
not invent absent clauses or penalty amounts. A question about regulatory
compliance (for example RGPD compliance) stays bounded until a separate,
verified cross-agent regulatory composition exists.

Document, version, analysis, and Contract Agent access all require active
project membership and existing document-visibility checks. Knowledge of an
identifier is not authorization. OCR runs only from a server-side extraction
job created after the authenticated document-upload path has applied those
authorization and malware gates.

## Limitations

- OCR may contain recognition errors; its source method is surfaced with the
  relevant passage.
- A semantic model can fail, time out, or return malformed output; this yields
  a partial or failed analysis rather than synthetic risk findings.
- Contract type and expected-provision completeness require contextual review.
- RegBridge does not replace qualified legal advice.
