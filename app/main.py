from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import get_settings
from app.rag.answerer import Answerer
from app.rag.embedder import StubEmbedder
from app.rag.llm import OpenAILLM, StubLLM
from app.rag.store_factory import get_store


app = FastAPI(title="JuCity AI Manager", version="0.1.0")

_settings = get_settings()
_embedder = StubEmbedder()
_store = get_store(_settings, vector_size=_embedder.dim)
_llm = OpenAILLM(model=_settings.openai_chat_model) if (os.getenv("OPENAI_API_KEY") or "") else StubLLM()
_answerer = Answerer(store=_store, embedder=_embedder, llm=_llm, top_k=_settings.top_k)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[str]


@app.get("/health")
def health() -> dict[str, str]:
    if _settings.vector_backend == "qdrant":
        try:
            _store.client.get_collections()  # type: ignore[attr-defined]
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


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    result = _answerer.answer(payload.question)
    return AskResponse(answer=result.answer, sources=result.sources)
