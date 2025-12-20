from __future__ import annotations

import sys
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

from app.config import get_settings
from app.rag.chunker import chunk_markdown
from app.rag.embedder import OpenAIEmbedder
from app.rag.kb_loader import load_kb_markdown
from app.rag.store_factory import get_store


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _batched(items: list[dict], batch_size: int) -> list[list[dict]]:
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


def main() -> int:
    settings = get_settings()
    kb_root = Path("kb/nn")

    embedder = OpenAIEmbedder(settings)

    docs = load_kb_markdown(kb_root)
    chunks: list[tuple[str, str | None, str]] = []
    # (file_path, heading, chunk_id, text) without storing whole Chunk class in this script.

    for doc in docs:
        for c in chunk_markdown(file_path=doc.file_path, markdown=doc.text):
            chunks.append((c.file_path, c.heading, c.chunk_id, c.text))

    if not chunks:
        print("OK: no chunks to index (kb/nn has no .md content).")
        return 0

    first_vector = embedder.embed([chunks[0][3]])[0]
    vector_size = len(first_vector)
    collection_name = "kb_nn"

    store = get_store(settings, vector_size=vector_size)

    try:
        store.recreate_collection(collection_name, vector_size)
    except Exception as exc:
        if settings.vector_backend == "qdrant":
            print(
                "ERROR: Qdrant is not reachable. "
                "Start Qdrant (docker compose up -d) or set QDRANT_URL to a reachable host.\n"
                f"QDRANT_URL={settings.qdrant_url}\n"
                f"Details: {type(exc).__name__}: {exc}"
            )
            return 1
        raise

    batch_size = 64
    points_indexed = 0
    for batch in _batched(
        [
            {
                "file_path": file_path,
                "heading": heading,
                "chunk_id": chunk_id,
                "text": text,
            }
            for file_path, heading, chunk_id, text in chunks
        ],
        batch_size=batch_size,
    ):
        texts = [b["text"] for b in batch]
        vectors = embedder.embed(texts)

        points: list[dict] = []
        for b, vector in zip(batch, vectors, strict=True):
            points.append(
                {
                    "id": _point_id(str(b["chunk_id"])),
                    "vector": vector,
                    "payload": {
                        "text": str(b["text"]),
                        "metadata": {
                            "file_path": str(b["file_path"]),
                            "heading": b["heading"],
                            "chunk_id": str(b["chunk_id"]),
                        },
                    },
                }
            )

        try:
            store.upsert(points)
            points_indexed += len(points)
        except Exception as exc:
            if settings.vector_backend == "qdrant":
                print(
                    "ERROR: failed to upsert into Qdrant. "
                    "Check Qdrant is running and reachable.\n"
                    f"QDRANT_URL={settings.qdrant_url}\n"
                    f"Details: {type(exc).__name__}: {exc}"
                )
                return 1
            raise

    print(f"OK: indexed {points_indexed} chunks into collection '{collection_name}' using {settings.vector_backend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
