# SCRUM-208 Research Document Foundation

SCRUM-208 provides the private, reproducible source boundary for later
research extraction:

`ResearcherProfile -> ResearchOutput -> immutable ResearchOutputVersion -> private DocumentVersion`

- A researcher profile belongs to one authenticated user.
- Authors, rights holder, licence, and visibility are declarations supplied by
  the researcher; RegBridge does not infer authorship or make legal validity
  determinations.
- Full research documents are private by default and have no anonymous/public
  full-text endpoint in this ticket.
- Each upload creates a new integer version and preserves the previous source.
  The database enforces unique version numbers per research output.
- Each version exposes a stable research-output version ID, the underlying
  immutable document-version ID, and a SHA-256 content hash for future
  evidence-constrained extraction.
- Missing `rights_holder` or `licence` is reported as `INCOMPLETE` and makes
  `publication_ready` false. `COMPLETE` only means the required RegBridge
  metadata fields are present; it is not legal verification or automatic
  publication.
- SCRUM-208 performs no AI extraction, abstract generation, embeddings,
  semantic search, matching, or public discovery publication. SCRUM-209 owns
  evidence locators and extraction against one exact immutable version.

The existing private document storage, validation, checksum, scan, download,
authorization, and audit infrastructure is reused. Storage keys and private
document contents are not exposed in research metadata responses or audit
payloads.
