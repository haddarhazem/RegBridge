from types import SimpleNamespace

import pytest

from app.modules.regulatory.retrieval import RegulatoryRetriever, RegulatoryRetrievalError, resolve_organization


class FakeEmbedder:
    def __init__(self, vector):
        self.vector = vector
        self.questions = []

    def encode(self, question):
        self.questions.append(question)
        return self.vector


class FakeQdrant:
    def __init__(self, points):
        self.points = points
        self.limit = None

    def query_points(self, collection_name, *, query, limit, with_payload, with_vectors):
        self.collection_name = collection_name
        self.limit = limit
        self.flags = (with_payload, with_vectors)
        return SimpleNamespace(points=self.points)


def point(point_id, domain="www.cnil.fr", content="evidence", score=0.9):
    return SimpleNamespace(id=point_id, score=score, payload={"source_domain": domain, "content": content, "chunk_index": 2, "url": "https://example.test/source"})


@pytest.mark.asyncio
async def test_retriever_uses_exactly_top_five_and_preserves_order():
    client = FakeQdrant([point("one"), point("two")])
    retriever = RegulatoryRetriever(embedder=FakeEmbedder([0.0] * 1024), client=client)

    result = await retriever.retrieve("question")

    assert client.collection_name == "reglementation_chunks"
    assert client.limit == 5
    assert client.flags == (True, False)
    assert [item.point_id for item in result] == ["one", "two"]
    assert [item.rank for item in result] == [1, 2]
    assert result[0].organization == "CNIL"


@pytest.mark.asyncio
async def test_retriever_skips_malformed_points_and_empty_content():
    client = FakeQdrant([SimpleNamespace(id="bad", score=0.9, payload={"source_domain": "cnil.fr"}), point("good")])
    retriever = RegulatoryRetriever(embedder=FakeEmbedder([0.0] * 1024), client=client)

    result = await retriever.retrieve("question")

    assert [item.point_id for item in result] == ["good"]


@pytest.mark.asyncio
async def test_retriever_rejects_wrong_embedding_dimension_and_qdrant_failure():
    retriever = RegulatoryRetriever(embedder=FakeEmbedder([0.0]), client=FakeQdrant([]))
    with pytest.raises(RegulatoryRetrievalError):
        await retriever.retrieve("question")

    class Broken:
        def encode(self, question):
            raise RuntimeError("offline")

    with pytest.raises(RegulatoryRetrievalError):
        await RegulatoryRetriever(embedder=Broken(), client=FakeQdrant([])).retrieve("question")


@pytest.mark.parametrize("domain, expected", [
    ("www.cnil.fr", "CNIL"),
    ("CNIL.FR.", "CNIL"),
    ("entreprendre.service-public.gouv.fr", "Entreprendre Service-Public.fr"),
    ("www.bpifrance-creation.fr", "Bpifrance Création"),
    ("UNKNOWN.EXAMPLE.FR", "unknown.example.fr"),
    (None, "unknown source"),
])
def test_organization_mapping(domain, expected):
    assert resolve_organization(domain) == expected
