# RD-017 — Investor opportunity brief generation

Status: selected for SCRUM-204.

Select deterministic V0 generation from the authorized `BriefEvidenceBundle`.
The bundle contains only the exact investor thesis snapshot, the authorized
startup snapshot, confirmed/corrected project facts, and the canonical
SCRUM-203 matching result. Missing information and the disclaimer are
application-owned.

V0 has complete controlled evidence for the SCRUM-204 production path. It is
the selected strategy and does not require provider availability. The brief is
generated from the exact authorized thesis/startup/matching snapshots and is
persisted as DRAFT.

Mistral native JSON_SCHEMA V1 remains an optional explanation candidate. The
original EX-022 V1 result was affected by a contract mismatch: free-form
thesis-fit text was validated as if it contained canonical dimension/outcome
literals. The corrected contract uses typed matching acknowledgements and
allowlisted typed evidence references, with structured comparison against the
canonical result. The corrected live smoke loaded `MISTRAL_API_KEY` through
the project Settings path and instantiated the provider, but the provider was
unavailable for the request; it therefore does not establish V1 quality. The
provider may never change deterministic
matching outcomes or facts. Provider, schema, timeout, and validator failures
use the deterministic template.

V0 remains selected for production. A credentialed corrected-contract V1
evaluation is required before reconsidering that decision. The incomplete V1
live evaluation does not block SCRUM-204 because production does not invoke
Mistral.

Briefs are persisted as DRAFT or UNVERIFIED and are not automatically shared.
SCRUM-205 factual verification and SCRUM-206 review/version workflow remain
separate tickets.
