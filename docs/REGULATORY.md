# Production regulatory capability

SCRUM-184 follows [RD-003](engineering-research/decisions/RD-003-regulatory-retrieval.md): direct BGE-M3 query encoding, 1024-dimensional cosine vectors, read-only Qdrant collection `reglementation_chunks`, and exactly top-k=5.

`RegulatoryRetriever` preserves point ID, URL, source domain, parent URL,
chunk index, rank, score, organization, and content internally. Public
responses expose only deterministic organization names such as `CNIL`,
`Entreprendre Service-Public.fr`, and `Bpifrance Création`.

Regulatory generation depends on the provider-neutral `LLMProvider` protocol.
The first implementation is `MistralLLMProvider`, configured with
`MISTRAL_API_KEY` and `MISTRAL_MODEL` through Settings. Credentials are never
included in agent requests or traces. Tests use fake providers and do not call
Mistral or Qdrant. Reranking, hybrid retrieval, query rewriting, and answer
verification remain out of scope.
