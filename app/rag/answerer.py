from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
        query_vec = self.embedder.embed([question])[0]
        hits = self.store.search(query_vec, self.top_k)

        context_chunks: list[dict] = []
        for h in hits:
            payload = h.get("payload") or {}
            meta = payload.get("metadata") or {}
            file_path = str(meta.get("file_path") or "")
            heading = meta.get("heading")
            chunk_id = str(meta.get("chunk_id") or "")
            text = str(payload.get("text") or "")
            if not file_path or not text:
                continue
            context_chunks.append(
                {
                    "file_path": file_path,
                    "heading": heading,
                    "chunk_id": chunk_id,
                    "text": text,
                }
            )

        # Ensure contacts are available for fallback answers ("уточнить у администратора/отдела праздников").
        contacts_path = Path("kb/nn/core/contacts.md")
        if contacts_path.exists():
            contacts_text = contacts_path.read_text(encoding="utf-8").strip()
            if contacts_text:
                already = any(c.get("file_path") == "kb/nn/core/contacts.md" for c in context_chunks)
                if not already:
                    context_chunks.append(
                        {
                            "file_path": "kb/nn/core/contacts.md",
                            "heading": "Контакты",
                            "chunk_id": "kb/nn/core/contacts.md::manual",
                            "text": contacts_text,
                        }
                    )

        sources: list[str] = []
        seen: set[str] = set()
        for ch in context_chunks:
            file_path = str(ch.get("file_path") or "")
            if file_path and file_path not in seen:
                seen.add(file_path)
                sources.append(file_path)

        answer = self.llm.generate(
            system_prompt=SYSTEM_PROMPT_JUICY_V1,
            context_chunks=context_chunks,
            user_question=question,
        )
        return AnswerResult(answer=answer, sources=sources)
