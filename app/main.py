from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

from app.config import get_settings
from app.rag.answerer import OpenAIAnswerer
from app.rag.embedder import OpenAIEmbedder
from app.rag.store_factory import get_store
from app.rag.prompts import SYSTEM_PROMPT_JUICY_V1


app = FastAPI(title="JuCity AI Manager", version="0.1.0")

_settings = get_settings()


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[str]


@app.get("/health")
def health() -> dict[str, str]:
    if _settings.vector_backend == "qdrant":
        try:
            store = get_store(_settings, vector_size=1)
            store.client.get_collections()  # type: ignore[attr-defined]
            return {"status": "ok", "backend": "qdrant"}
        except Exception:
            return {"status": "error", "backend": "qdrant"}

    if _settings.vector_backend == "chroma":
        try:
            from pathlib import Path

            Path(_settings.chroma_dir).mkdir(parents=True, exist_ok=True)
            return {"status": "ok", "backend": "chroma"}
        except Exception as exc:
            return {"status": "error", "backend": "chroma", "detail": f"{type(exc).__name__}: {exc}"}

    return {"status": "error", "backend": _settings.vector_backend, "detail": "unknown VECTOR_BACKEND"}


def _read_contacts() -> str:
    contacts_path = Path("kb/nn/core/contacts.md")
    if not contacts_path.exists():
        return ""
    return contacts_path.read_text(encoding="utf-8").strip()


def _fallback_answer_with_contacts(contacts_text: str) -> str:
    base = "Лучше уточнить у администратора/отдела праздников."
    if not contacts_text:
        return base
    return f"{base}\n\nКонтакты:\n{contacts_text}"


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    if not _settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is required for /ask")

    embedder = OpenAIEmbedder(_settings)
    query_vec = embedder.embed([payload.question])[0]

    store = get_store(_settings, vector_size=len(query_vec))

    top_k = 8
    try:
        hits = store.search(query_vec, top_k)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        if "dimension" in str(exc).lower():
            detail += " (possible embedding/index dimension mismatch — run: python scripts/reindex_nn.py)"
        raise HTTPException(status_code=500, detail=detail)

    candidates: list[dict] = []
    for h in hits:
        score = float(h.get("score") or 0.0)
        p = h.get("payload") or {}
        text = p.get("text")
        metadata = p.get("metadata")
        if not text or not metadata:
            continue
        candidates.append({"score": score, "text": text, "metadata": metadata})

    candidates.sort(key=lambda x: x["score"], reverse=True)

    similarity_threshold = 0.25
    filtered = [c for c in candidates if c["score"] >= similarity_threshold]
    filtered = filtered[:6]

    if len(filtered) < 2:
        contacts_text = _read_contacts()
        best_chunk = candidates[0] if candidates else None

        sources: list[str] = ["kb/nn/core/contacts.md"] if contacts_text else []
        if best_chunk:
            fp = str((best_chunk.get("metadata") or {}).get("file_path") or "")
            if fp and fp not in sources:
                sources.append(fp)
        return AskResponse(answer=_fallback_answer_with_contacts(contacts_text), sources=sources)

    context_chunks = [{"text": c["text"], "metadata": c["metadata"]} for c in filtered]

    answerer = OpenAIAnswerer(_settings)
    result = answerer.generate(SYSTEM_PROMPT_JUICY_V1, context_chunks, payload.question)
    return AskResponse(answer=str(result.get("answer") or ""), sources=list(result.get("sources") or []))
