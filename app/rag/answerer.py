from __future__ import annotations

from dataclasses import dataclass

from app.rag.embedder import Embedder
from app.rag.llm import LLM
from app.rag.prompts import SYSTEM_PROMPT_JUICY_V1
from app.rag.qdrant_store import QdrantStore


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    sources: list[str]


class Answerer:
    def __init__(self, *, store: QdrantStore, embedder: Embedder, llm: LLM, top_k: int = 5) -> None:
        self.store = store
        self.embedder = embedder
        self.llm = llm
        self.top_k = top_k

    def answer(self, question: str) -> AnswerResult:
        query_vec = self.embedder.embed_texts([question])[0]
        hits = self.store.search(query_vector=query_vec, limit=self.top_k)

        sources: list[str] = []
        seen: set[str] = set()
        for h in hits:
            if h.file_path and h.file_path not in seen:
                seen.add(h.file_path)
                sources.append(h.file_path)

        context = "\n\n".join(
            f"[{h.file_path} | {h.heading or '—'}]\n{h.text}" for h in hits if h.text and h.file_path
        )
        answer = self.llm.generate(system_prompt=SYSTEM_PROMPT_JUICY_V1, question=question, context=context)
        return AnswerResult(answer=answer, sources=sources)

