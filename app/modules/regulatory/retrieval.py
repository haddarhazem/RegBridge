"""Read-only BGE-M3 dense retrieval for the frozen regulatory collection."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol

from qdrant_client import QdrantClient

from app.core.config import Settings, get_settings
from app.modules.regulatory.contracts import RegulatoryEvidence


class RegulatoryRetrievalError(RuntimeError):
    """Controlled retrieval failure."""


class RegulatoryConfigurationError(RegulatoryRetrievalError):
    """Retrieval configuration is incomplete or invalid."""


class QueryEmbedder(Protocol):
    def encode(self, question: str) -> list[float]: ...


class QdrantSearchClient(Protocol):
    def query_points(self, collection_name: str, *, query: list[float], limit: int, with_payload: bool, with_vectors: bool) -> Any: ...


class BGEQueryEncoder:
    def __init__(self, *, model_name: str, device: str) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(device).eval()
        self.device = device

    def encode(self, question: str) -> list[float]:
        batch = self.tokenizer([question], padding=True, truncation=True, return_tensors="pt").to(self.device)
        with self._torch.inference_mode():
            output = self.model(**batch).last_hidden_state
        mask = batch["attention_mask"].unsqueeze(-1).expand(output.size()).float()
        vector = (output * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
        values = self._torch.nn.functional.normalize(vector, p=2, dim=1)[0].cpu().tolist()
        if len(values) != 1024:
            raise RegulatoryRetrievalError("Regulatory query embedding has an invalid dimension")
        return values


def resolve_organization(source_domain: str | None) -> str:
    normalized = (source_domain or "").strip().lower().rstrip(".")
    mapping = {
        "www.cnil.fr": "CNIL",
        "cnil.fr": "CNIL",
        "entreprendre.service-public.gouv.fr": "Entreprendre Service-Public.fr",
        "www.bpifrance-creation.fr": "Bpifrance Création",
        "bpifrance-creation.fr": "Bpifrance Création",
    }
    return mapping.get(normalized, normalized or "unknown source")


def _point_values(point: Any) -> tuple[str, float, dict[str, Any]] | None:
    point_id = getattr(point, "id", None)
    payload = getattr(point, "payload", None)
    score = getattr(point, "score", None)
    if point_id is None or not isinstance(payload, dict) or not isinstance(score, (int, float)):
        return None
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    return str(point_id), float(score), payload


class RegulatoryRetriever:
    top_k = 5
    vector_dimension = 1024

    def __init__(self, *, embedder: QueryEmbedder, client: QdrantSearchClient, collection: str = "reglementation_chunks") -> None:
        self.embedder = embedder
        self.client = client
        self.collection = collection

    async def retrieve(self, question: str) -> list[RegulatoryEvidence]:
        try:
            vector = self.embedder.encode(question)
            if len(vector) != self.vector_dimension:
                raise RegulatoryRetrievalError("Regulatory query embedding has an invalid dimension")
            response = self.client.query_points(
                self.collection,
                query=vector,
                limit=self.top_k,
                with_payload=True,
                with_vectors=False,
            )
            points = getattr(response, "points", [])
        except RegulatoryRetrievalError:
            raise
        except Exception as exc:
            raise RegulatoryRetrievalError("Regulatory retrieval service is unavailable") from exc

        evidence: list[RegulatoryEvidence] = []
        for rank, point in enumerate(points[: self.top_k], start=1):
            values = _point_values(point)
            if values is None:
                continue
            point_id, score, payload = values
            evidence.append(RegulatoryEvidence(
                point_id=point_id,
                rank=rank,
                retrieval_score=score,
                organization=resolve_organization(payload.get("source_domain")),
                source_domain=payload.get("source_domain") if isinstance(payload.get("source_domain"), str) else None,
                url=payload.get("url") if isinstance(payload.get("url"), str) else None,
                parent_url=payload.get("parent_url") if isinstance(payload.get("parent_url"), str) else None,
                chunk_index=payload.get("chunk_index") if isinstance(payload.get("chunk_index"), int) and payload.get("chunk_index") >= 0 else None,
                content=payload["content"].strip()[:12000],
            ))
        return evidence


def _secret_value(value: Any) -> str | None:
    return value.get_secret_value() if value is not None and hasattr(value, "get_secret_value") else value


@lru_cache(maxsize=1)
def get_regulatory_retriever() -> RegulatoryRetriever:
    settings: Settings = get_settings()
    if not settings.qdrant_url or not _secret_value(settings.qdrant_api_key):
        raise RegulatoryConfigurationError("Regulatory retrieval is not configured")
    client = QdrantClient(url=settings.qdrant_url, api_key=_secret_value(settings.qdrant_api_key), timeout=30)
    try:
        embedder = BGEQueryEncoder(model_name=settings.bge_m3_model_name, device=settings.bge_m3_device)
    except Exception as exc:
        raise RegulatoryRetrievalError("Regulatory embedding service is unavailable") from exc
    return RegulatoryRetriever(embedder=embedder, client=client, collection=settings.qdrant_collection)
