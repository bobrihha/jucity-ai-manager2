from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import get_settings
from app.rag.answerer import Answerer
from app.rag.embedder import StubEmbedder
from app.rag.llm import StubLLM
from app.rag.qdrant_store import QdrantStore


app = FastAPI(title="JuCity AI Manager", version="0.1.0")

_settings = get_settings()
_embedder = StubEmbedder()
_store = QdrantStore(
    url=_settings.qdrant_url,
    api_key=_settings.qdrant_api_key,
    collection=_settings.qdrant_collection,
    vector_size=_embedder.dim,
)
_llm = StubLLM()
_answerer = Answerer(store=_store, embedder=_embedder, llm=_llm, top_k=_settings.top_k)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[str]


@app.get("/health")
def health() -> dict[str, str]:
    try:
        _store.client.get_collections()
        return {"status": "ok"}
    except Exception:
        return {"status": "error"}


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    result = _answerer.answer(payload.question)
    return AskResponse(answer=result.answer, sources=result.sources)
