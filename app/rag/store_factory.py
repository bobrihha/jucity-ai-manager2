from __future__ import annotations

from typing import Protocol

from app.config import Settings
from app.rag.chroma_store import ChromaStore
from app.rag.qdrant_store import QdrantStore


class VectorStore(Protocol):
    def recreate_collection(self, collection_name: str, vector_size: int) -> None: ...

    def upsert(self, points: list[dict]) -> None: ...

    def search(self, query_vector: list[float], top_k: int) -> list[dict]: ...


def get_store(settings: Settings, *, vector_size: int = 8) -> VectorStore:
    if settings.vector_backend == "qdrant":
        return QdrantStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            collection=settings.qdrant_collection,
            vector_size=vector_size,
        )
    if settings.vector_backend == "chroma":
        return ChromaStore(persist_dir=settings.chroma_dir, collection=settings.qdrant_collection)
    raise ValueError('VECTOR_BACKEND must be "qdrant" or "chroma"')

