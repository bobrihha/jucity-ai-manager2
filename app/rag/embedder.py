from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self.embed(texts)

class OpenAIEmbedder(Embedder):
    def __init__(self, settings) -> None:
        if TYPE_CHECKING:  # pragma: no cover
            from app.config import Settings  # noqa: F401

        self.api_key = getattr(settings, "openai_api_key", None)
        self.model = getattr(settings, "openai_embedding_model", "text-embedding-3-small")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required")

        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=self.api_key)

        normalized = [(t if t.strip() else " ") for t in texts]
        vectors: list[list[float]] = []

        batch_size = 96
        for i in range(0, len(normalized), batch_size):
            batch = normalized[i : i + batch_size]
            resp = client.embeddings.create(model=self.model, input=batch)
            data = list(resp.data)
            data.sort(key=lambda x: x.index)
            for item in data:
                vec = list(item.embedding)
                vectors.append(vec)

        return vectors
