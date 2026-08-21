"""Read-only Qdrant boundary for EX-002."""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient


class ReadOnlyQdrantReader:
    """Expose only non-mutating collection and retrieval operations."""

    def __init__(self, client: QdrantClient, collection: str) -> None:
        self.client = client
        self.collection = collection

    def get_collection_info(self):
        return self.client.get_collection(self.collection)

    def count(self, *, exact: bool = False) -> int:
        return self.client.count(self.collection, exact=exact).count

    def scroll(self, *, limit: int = 100):
        return self.client.scroll(self.collection, limit=limit, with_payload=True, with_vectors=False)

    def retrieve(self, point_ids: list[str]):
        return self.client.retrieve(self.collection, ids=point_ids, with_payload=True, with_vectors=False)

    def search(self, vector: list[float], *, limit: int):
        return self.client.query_points(self.collection, query=vector, limit=limit, with_payload=True, with_vectors=False).points

