from __future__ import annotations

from dataclasses import dataclass
import os


BUILD_ID = os.getenv("BUILD_ID", "dev")


@dataclass(frozen=True)
class Settings:
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    top_k: int
    vector_backend: str
    chroma_dir: str
    openai_api_key: str | None
    openai_embedding_model: str
    openai_chat_model: str


def get_settings() -> Settings:
    return Settings(
        # Default to localhost for docker-compose usage; override via QDRANT_URL for external host/IP.
        qdrant_url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "kb_nn"),
        top_k=int(os.getenv("TOP_K", "5")),
        vector_backend=os.getenv("VECTOR_BACKEND", "chroma"),
        chroma_dir=os.getenv("CHROMA_DIR", "data/chroma_nn"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
    )
