from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.config import Settings
from app.rag.embedder import Embedder
from app.rag.prompts import SYSTEM_PROMPT_JUICY_V1
from app.rag.store_factory import VectorStore


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    sources: list[str]


class AnswerGenerator(Protocol):
    def generate(self, system_prompt: str, context_chunks: list[dict], user_question: str) -> dict: ...


class OpenAIAnswerer:
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required")
        self._api_key = settings.openai_api_key
        self._model = settings.openai_chat_model
        self._temperature = 0.4
        self._max_tokens = 500

    def generate(self, system_prompt: str, context_chunks: list[dict], user_question: str) -> dict:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=self._api_key)

        sources: list[str] = []
        seen: set[str] = set()
        facts_lines: list[str] = []
        for idx, ch in enumerate(context_chunks, start=1):
            meta = ch.get("metadata") or {}
            file_path = str(meta.get("file_path") or "")
            text = str(ch.get("text") or "")
            if file_path and file_path not in seen:
                seen.add(file_path)
                sources.append(file_path)
            facts_lines.append(f"{idx}) [{file_path}] {text}")

        user_content = (
            f"Вопрос гостя: {user_question}\n\n"
            "ФАКТЫ ИЗ БАЗЫ (используй ТОЛЬКО их, не выдумывай):\n"
            + "\n".join(facts_lines)
            + "\n\n"
            "ПРАВИЛА ОТВЕТА:\n"
            "- Если в фактах нет ответа: скажи, что лучше уточнить у администратора/отдела праздников и дай контакт из базы.\n"
            "- Не упоминай “ИИ/бот/LLM/модель/контекст/чанки/TODO”.\n"
            "- Пиши как Джуси: дружелюбно, живо, без канцелярита, но чётко.\n"
        )

        resp = client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        answer = (resp.choices[0].message.content or "").strip()
        return {"answer": answer, "sources": sources[:6]}


class StubAnswerer:
    def generate(self, system_prompt: str, context_chunks: list[dict], user_question: str) -> dict:
        sources: list[str] = []
        seen: set[str] = set()
        for ch in context_chunks:
            file_path = str(ch.get("file_path") or "")
            if file_path and file_path not in seen:
                seen.add(file_path)
                sources.append(file_path)
            if len(sources) >= 6:
                break

        answer = (
            "Подскажу по базе знаний парка. "
            "Я нашёл подходящие источники — посмотрите их, и если нужно, я помогу ответить точнее."
        )
        return {"answer": answer, "sources": sources}


class Answerer:
    def __init__(
        self,
        *,
        store: VectorStore,
        embedder: Embedder,
        generator: AnswerGenerator,
        top_k: int = 5,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.generator = generator
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

        result = self.generator.generate(SYSTEM_PROMPT_JUICY_V1, context_chunks, question)
        return AnswerResult(answer=str(result.get("answer") or ""), sources=list(result.get("sources") or []))
