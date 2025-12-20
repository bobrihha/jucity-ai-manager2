from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm


@dataclass(frozen=True)
class SearchHit:
    file_path: str
    heading: str | None
    chunk_id: str
    text: str
    score: float


class QdrantStore:
    def __init__(self, *, url: str, api_key: str | None, collection: str, vector_size: int) -> None:
        self.collection = collection
        self.vector_size = vector_size
        self.client = QdrantClient(url=url, api_key=api_key)

    def ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        if any(c.name == self.collection for c in collections):
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=qm.VectorParams(size=self.vector_size, distance=qm.Distance.COSINE),
        )

    def recreate_collection(self) -> None:
        self.client.recreate_collection(
            collection_name=self.collection,
            vectors_config=qm.VectorParams(size=self.vector_size, distance=qm.Distance.COSINE),
        )

    def upsert(self, *, points: list[dict[str, Any]]) -> None:
        self.ensure_collection()
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, *, query_vector: list[float], limit: int = 5) -> list[SearchHit]:
        self.ensure_collection()
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
        )
        hits: list[SearchHit] = []
        for r in results:
            payload = r.payload or {}
            hits.append(
                SearchHit(
                    file_path=str(payload.get("file_path", "")),
                    heading=payload.get("heading"),
                    chunk_id=str(payload.get("chunk_id", "")),
                    text=str(payload.get("text", "")),
                    score=float(r.score or 0.0),
                )
            )
        return hits

