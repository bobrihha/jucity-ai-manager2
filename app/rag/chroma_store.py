from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    score: float
    payload: dict[str, Any]


class ChromaStore:
    def __init__(self, *, persist_dir: str = "data/chroma_nn", collection: str = "kb_nn") -> None:
        self.persist_dir = Path(persist_dir)
        self.collection = collection
        self.vector_size: int | None = None

    def _client(self):
        import chromadb  # type: ignore

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(self.persist_dir))

    def _get_collection(self):
        client = self._client()
        # Prefer cosine to match Qdrant defaults in this repo.
        return client.get_or_create_collection(
            name=self.collection,
            metadata={"hnsw:space": "cosine"},
        )

    def recreate_collection(self, collection_name: str, vector_size: int) -> None:
        self.collection = collection_name
        self.vector_size = int(vector_size)

        client = self._client()
        try:
            client.delete_collection(name=self.collection)
        except Exception:
            pass
        client.create_collection(name=self.collection, metadata={"hnsw:space": "cosine"})

    def upsert(self, points: list[dict]) -> None:
        col = self._get_collection()

        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for p in points:
            payload = p.get("payload") or {}
            metadata = payload.get("metadata") or {}
            ids.append(str(p["id"]))
            embeddings.append(list(p["vector"]))
            documents.append(str(payload.get("text", "")))
            metadatas.append(
                {
                    "file_path": metadata.get("file_path"),
                    "heading": metadata.get("heading"),
                    "chunk_id": metadata.get("chunk_id"),
                }
            )

        if not ids:
            return

        col.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    def search(self, query_vector: list[float], top_k: int) -> list[dict]:
        col = self._get_collection()
        res = col.query(
            query_embeddings=[query_vector],
            n_results=int(top_k),
            include=["documents", "metadatas", "distances"],
        )

        documents = (res.get("documents") or [[]])[0]
        metadatas = (res.get("metadatas") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]

        out: list[dict] = []
        for doc, meta, dist in zip(documents, metadatas, distances, strict=False):
            distance = float(dist) if dist is not None else 0.0
            score = 1.0 - distance
            out.append(
                {
                    "score": score,
                    "payload": {
                        "text": doc,
                        "metadata": {
                            "file_path": (meta or {}).get("file_path"),
                            "heading": (meta or {}).get("heading"),
                            "chunk_id": (meta or {}).get("chunk_id"),
                        },
                    },
                }
            )
        return out

