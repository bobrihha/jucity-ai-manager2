from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import re
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

_DIRECT_INTENT_FILES: dict[str, list[str]] = {
    "hours": ["kb/nn/core/hours.md", "kb/nn/core/contacts.md"],
    "prices": ["kb/nn/tickets/prices.md", "kb/nn/tickets/free_entry.md", "kb/nn/core/contacts.md"],
    "discounts": ["kb/nn/tickets/discounts.md", "kb/nn/tickets/after_20.md", "kb/nn/core/contacts.md"],
    "vr": ["kb/nn/services/vr.md", "kb/nn/core/contacts.md"],
    "phygital": ["kb/nn/services/phygital.md", "kb/nn/core/contacts.md"],
    "own_food_rules": ["kb/nn/food/own_food_rules.md", "kb/nn/parties/birthday.md", "kb/nn/core/contacts.md"],
}


def build_direct_context(intent: str) -> list[dict]:
    files = _DIRECT_INTENT_FILES.get(intent, [])
    chunks: list[dict] = []

    for idx, file_path in enumerate(files):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
        except FileNotFoundError:
            logging.warning("build_direct_context: file not found: %s", file_path)
            continue
        except Exception as exc:
            logging.warning("build_direct_context: failed to read %s (%s: %s)", file_path, type(exc).__name__, exc)
            continue

        chunks.append(
            {
                "text": text,
                "metadata": {"file_path": file_path, "heading": "FULLFILE", "chunk_id": f"direct-{idx}"},
            }
        )

    return chunks


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
        facts_lines: list[str] = []
        for idx, ch in enumerate(context_chunks, start=1):
            meta = ch.get("metadata") or {}
            file_path = str(meta.get("file_path") or "")
            text = str(ch.get("text") or "")
            if file_path and file_path not in sources:
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
        answer = (resp.choices[0].message.content or "")
        answer = answer.strip()
        answer = answer.replace("\n\n\n", "\n\n")
        if answer.startswith("nЕсли"):
            answer = "Если" + answer[len("nЕсли") :]

        def _format_phone(m: re.Match[str]) -> str:
            digits = m.group(1)
            return f"+7 {digits[0:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"

        answer = re.sub(r"\+7(\d{10})\b", _format_phone, answer)

        # If context contains a directly relevant link (e.g. VR prices), include it (max 1 link).
        # This helps enforce the product rule even if the model answers "могу прислать".
        if "http" not in answer.lower():
            question_low = user_question.lower()
            context_text = "\n\n".join(str(c.get("text") or "") for c in context_chunks)
            if "vr" in question_low and "https://nn.jucity.ru/tickets-vr/" in context_text:
                answer = f"{answer}\n\nhttps://nn.jucity.ru/tickets-vr/"

        if not answer or len(answer) < 10:
            first = context_chunks[0] if context_chunks else {}
            first_text = str(first.get("text") or "").strip()
            first_text = first_text.replace("\n\n\n", "\n\n")
            excerpt = first_text[:320].strip()
            if excerpt and len(first_text) > 320:
                excerpt = excerpt + "…"

            contacts_text = ""
            try:
                p = Path("kb/nn/core/contacts.md")
                if p.exists():
                    contacts_text = p.read_text(encoding="utf-8").strip()
            except Exception:
                contacts_text = ""

            fallback = "Лучше уточнить у администратора/отдела праздников."
            if excerpt:
                fallback = f"{excerpt}\n\n{fallback}"
            if contacts_text:
                fallback = f"{fallback}\n\nКонтакты:\n{contacts_text}"

            answer = fallback

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
