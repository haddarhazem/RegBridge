# Research discovery approval boundary

SCRUM-209 extraction runs are generated proposals. SCRUM-210 creates a
separate, immutable discovery version from one exact extraction run. A
researcher correction creates a new `DRAFT` version; it never mutates the
parent and approval never carries forward.

Approval is distinct from publication and matching. All fields default to
`PRIVATE`. A visitor receives only fields explicitly marked `PUBLIC` from an
`APPROVED` version, and the full research document and evidence context remain
private. `MATCHABLE` is stored for the later SCRUM-211 projection and is not
used by SCRUM-210.

Corrections remain source-backed: factual values must already be present in the
exact extraction evidence for the version. Unsupported additions, numeric
changes and invented claims are rejected. The abstract is rebuilt
deterministically from approved source-backed fields; no second LLM is used.

Rights metadata may block public eligibility while still allowing private
content approval. No SCRUM-210 endpoint approves, publishes or matches the
underlying research document.
