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

    def recreate_collection(self, collection_name: str, vector_size: int) -> None:
        self.collection = collection_name
        self.vector_size = int(vector_size)
        self.client.recreate_collection(
            collection_name=self.collection,
            vectors_config=qm.VectorParams(size=self.vector_size, distance=qm.Distance.COSINE),
        )

    def upsert(self, *, points: list[dict[str, Any]]) -> None:
        self.ensure_collection()
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, query_vector: list[float], top_k: int) -> list[dict]:
        self.ensure_collection()
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=int(top_k),
            with_payload=True,
        )
        out: list[dict] = []
        for r in results:
            payload = r.payload or {}

            # Support both payload layouts:
            # 1) {"text": "...", "metadata": {...}}
            # 2) {"text": "...", "file_path": "...", "heading": "...", "chunk_id": "..."}
            metadata = payload.get("metadata") or {}
            file_path = metadata.get("file_path") or payload.get("file_path") or ""
            heading = metadata.get("heading") if metadata else payload.get("heading")
            chunk_id = metadata.get("chunk_id") or payload.get("chunk_id") or ""
            text = payload.get("text") or ""

            out.append(
                {
                    "score": float(r.score or 0.0),
                    "payload": {
                        "text": str(text),
                        "metadata": {
                            "file_path": str(file_path),
                            "heading": heading,
                            "chunk_id": str(chunk_id),
                        },
                    },
                }
            )
        return out
