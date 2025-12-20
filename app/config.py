from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    top_k: int


def get_settings() -> Settings:
    return Settings(
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "kb_nn"),
        top_k=int(os.getenv("TOP_K", "5")),
    )

