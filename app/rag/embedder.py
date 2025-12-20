from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
import os


class Embedder(ABC):
    @property
    @abstractmethod
    def dim(self) -> int: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self.embed(texts)


class StubEmbedder(Embedder):
    def __init__(self, dim: int = 8) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vec = []
            for i in range(self._dim):
                b = digest[i]
                vec.append((b / 255.0) * 2.0 - 1.0)
            vectors.append(vec)
        return vectors


class OpenAIEmbedder(Embedder):
    def __init__(self, *, model: str) -> None:
        self.model = model
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            raise RuntimeError("Embedding dimension is unknown until the first embed() call.")
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set. Set it to use OpenAI embeddings.")

        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)

        normalized = [(t if t.strip() else " ") for t in texts]
        vectors: list[list[float]] = []

        batch_size = 100
        for i in range(0, len(normalized), batch_size):
            batch = normalized[i : i + batch_size]
            resp = client.embeddings.create(model=self.model, input=batch)
            data = list(resp.data)
            data.sort(key=lambda x: x.index)
            for item in data:
                vec = list(item.embedding)
                vectors.append(vec)

        if vectors and self._dim is None:
            self._dim = len(vectors[0])
        return vectors

    @classmethod
    def from_settings(cls, settings) -> "OpenAIEmbedder":
        return cls(model=settings.openai_embedding_model)
