from __future__ import annotations

import sys
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.rag.chunker import chunk_markdown
from app.rag.embedder import StubEmbedder
from app.rag.kb_loader import load_kb_markdown
from app.rag.store_factory import get_store


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def main() -> int:
    settings = get_settings()
    kb_root = Path("kb/nn")

    embedder = StubEmbedder()
    store = get_store(settings, vector_size=embedder.dim)
    store.recreate_collection(settings.qdrant_collection, embedder.dim)

    docs = load_kb_markdown(kb_root)
    all_points: list[dict] = []

    for doc in docs:
        chunks = chunk_markdown(file_path=doc.file_path, markdown=doc.text)
        vectors = embedder.embed_texts([c.text for c in chunks]) if chunks else []
        for chunk, vector in zip(chunks, vectors, strict=True):
            all_points.append(
                {
                    "id": _point_id(chunk.chunk_id),
                    "vector": vector,
                    "payload": {
                        "text": chunk.text,
                        "metadata": {
                            "file_path": chunk.file_path,
                            "heading": chunk.heading,
                            "chunk_id": chunk.chunk_id,
                        },
                    },
                }
            )

    if all_points:
        store.upsert(points=all_points)

    print(f"OK: indexed {len(all_points)} chunks into collection '{settings.qdrant_collection}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
