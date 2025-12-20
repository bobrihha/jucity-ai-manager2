from __future__ import annotations

from dataclasses import dataclass

from app.rag.embedder import Embedder
from app.rag.llm import LLM
from app.rag.prompts import SYSTEM_PROMPT_JUICY_V1
from app.rag.store_factory import VectorStore


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    sources: list[str]


class Answerer:
    def __init__(self, *, store: VectorStore, embedder: Embedder, llm: LLM, top_k: int = 5) -> None:
        self.store = store
        self.embedder = embedder
        self.llm = llm
        self.top_k = top_k

    def answer(self, question: str) -> AnswerResult:
        query_vec = self.embedder.embed_texts([question])[0]
        hits = self.store.search(query_vec, self.top_k)

        sources: list[str] = []
        seen: set[str] = set()
        for h in hits:
            meta = (h.get("payload") or {}).get("metadata") or {}
            file_path = str(meta.get("file_path") or "")
            if file_path and file_path not in seen:
                seen.add(file_path)
                sources.append(file_path)

        context_blocks: list[str] = []
        for h in hits:
            payload = h.get("payload") or {}
            meta = payload.get("metadata") or {}
            file_path = str(meta.get("file_path") or "")
            heading = meta.get("heading") or "—"
            text = str(payload.get("text") or "")
            if file_path and text:
                context_blocks.append(f"[{file_path} | {heading}]\n{text}")

        context = "\n\n".join(context_blocks)
        answer = self.llm.generate(system_prompt=SYSTEM_PROMPT_JUICY_V1, question=question, context=context)
        return AnswerResult(answer=answer, sources=sources)
