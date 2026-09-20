# ADR-0007: Use a derived project knowledge graph as trusted supplemental context

## Status

Accepted for RegBridge V1.

## Context

Project descriptions are useful input, but they are not an explainable or
bounded representation of the confirmed structured knowledge held by
RegBridge. Entrepreneur, regulatory and future matching workflows need a
readable relationship view without creating a second mutable source of truth.

## Decision

PostgreSQL project records, confirmed/corrected project facts and authorized
document metadata remain the source of truth. RegBridge builds a small
deterministic project knowledge graph when requested; it is exposed through an
authorized read-model API and is not persisted independently.

The frontend consumes that read model for a project graph explorer. A bounded
trusted subgraph is supplemental context for agents through
`GraphContextProvider`. Only confirmed/corrected project knowledge is eligible;
pending and deleted facts are excluded. Qdrant remains the system for
documentary regulatory retrieval, and graph relationships never constitute
regulatory evidence.

### V1.1 semantic enrichment

V1.1 represents explicitly structured, confirmed profile values and confirmed
facts as bounded atomic concepts when their user-supplied syntax supports that
interpretation. Concepts have a type, canonical label, conservative normalized
key, provenance, and trust status. Normalization removes only spacing, case,
accents, and punctuation differences; it does not perform fuzzy or
embedding-based equivalence.

Candidate enrichment reuses `project_facts`, rather than creating graph facts
or a second source of truth. The built-in extractor accepts only explicitly
delimited technology/data lists and always creates `pending_confirmation`
facts. Editors must confirm, correct, or reject candidates through the existing
fact lifecycle. Narrative text is not sent to a provider and never becomes
trusted knowledge automatically. A future provider extractor must be explicit
opt-in, use the existing provider boundary, validate a fixed candidate schema,
and remain pending-only.

Verified regulatory assessment metadata may contribute an assessment and its
recorded evidence organizations. Regulatory domains are represented only when
an accepted assessment stored them explicitly. The graph never infers that a
technology or data category makes a regulation apply, and cannot replace
Qdrant or authoritative-source evidence in a regulatory answer.

The existing entrepreneur frontend is static browser JavaScript with no
frontend package/bundle pipeline. V1 therefore uses a small Canvas projection
with deterministic layout, pointer orbit, zoom, filtering and selection rather
than adding an unbundled third-party 3D dependency or changing the frontend
architecture solely for this view.

V1.1 does not add Neo4j, another graph database, LangGraph, GraphRAG, graph
embeddings, or a new orchestration framework. The 3D explorer is a consumer of
the derived graph, never its authoring system.

### V1.2 conversational knowledge evolution

Durable information stated by a user in a project-scoped Copilot conversation
may create a conservative `pending_confirmation` project fact. The built-in
conversation extractor is deterministic, processes user-authored messages
only, accepts a fixed ontology/relation vocabulary, and records bounded
conversation/message provenance. Assistant-generated text, questions,
hypotheticals and plans do not become project knowledge.

Conversation-derived candidates are never trusted automatically. The user must
confirm, correct, or reject them through the existing project-fact lifecycle;
only then can the derived graph and its bounded agent context include them.
Explicit removal proposals remain pending and, once confirmed, remove only an
exact matching trusted relation. Candidate extraction is independent of the
Copilot answer and cannot make an otherwise successful answer fail.

The generic `PROVIDER` node and `USES_PROVIDER` relation are included for
explicit infrastructure/hosting declarations. This is a project-local
relationship, not a regulatory conclusion or evidence. PostgreSQL remains the
only mutable source of truth; V1.2 does not introduce Neo4j, a graph database,
LangGraph, or a graph-RAG framework.

## Consequences

Positive:

- users can inspect what is known, connected, and sourced for their project;
- agents receive a bounded, explainable structural supplement;
- corrections are reflected automatically because there is no copied graph
  state.
- candidate confirmation, correction, and rejection automatically update the
  next graph read without a graph-mutation endpoint.

Negative:

- V1 supports only shallow, project-local traversal;
- relationship richness is limited to data currently stored and trusted.

## Revisit conditions

Revisit a dedicated graph database only if deep multi-hop traversal,
cross-project queries, operational graph algorithms, or graph size make the
derived PostgreSQL read model unsuitable. This decision does not change
ADR-0006: a knowledge graph represents data, not agent workflow control.
