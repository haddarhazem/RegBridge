# Research extraction production boundary

SCRUM-209 uses the RD-019-selected `extractive_evidence_locked` strategy.
Mistral selects only `status` and allowlisted deterministic source segment IDs;
it cannot provide authoritative factual values. The backend resolves those IDs
against the exact authorized `ResearchOutputVersion`, verifies the persisted
SHA-256, copies source text exactly, and builds the RegBridge Abstract
deterministically.

Extraction runs are immutable and remain `GENERATED` until SCRUM-210 review.
Each run records the exact research-output version, document version, source
hash, strategy metadata, selected source text, and evidence locator. Full
private source content remains in document storage and is not returned by the
extraction routes. Owner-scoped queries prevent cross-user and cross-version
access; GET and LIST read persisted runs and never recompute them.

Provider failures, including HTTP 429, fail safely with no fabricated result,
no prior-result reuse, and a failure audit event. No approval, publication, or
matching transition is exposed by SCRUM-209.

The R3C research limitation remains documented: four non-critical methodology
false positives were caused by wrong-field source selection. This does not
change the requirement for researcher review at SCRUM-210.
