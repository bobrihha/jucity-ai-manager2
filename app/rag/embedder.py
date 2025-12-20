from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod


class Embedder(ABC):
    @property
    @abstractmethod
    def dim(self) -> int: ...

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class StubEmbedder(Embedder):
    def __init__(self, dim: int = 8) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
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
    @property
    def dim(self) -> int:
        raise NotImplementedError("TODO: configure OpenAI embeddings and set correct vector size.")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("TODO: implement OpenAI embeddings via API client.")

