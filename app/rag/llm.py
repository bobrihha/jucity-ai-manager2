from __future__ import annotations

import os
from abc import ABC, abstractmethod


class LLM(ABC):
    @abstractmethod
    def generate(self, *, system_prompt: str, context_chunks: list[dict], user_question: str) -> str: ...


class StubLLM(LLM):
    def generate(self, *, system_prompt: str, context_chunks: list[dict], user_question: str) -> str:
        return (
            "Я могу подсказать по базе знаний Джунгли Сити (НН). "
            "Сейчас генерация ответа через LLM не подключена (TODO). "
            "Я нашёл релевантные источники — посмотрите их, и я помогу сформулировать ответ."
        )


class OpenAILLM(LLM):
    def __init__(self, *, model: str, temperature: float = 0.4) -> None:
        self.model = model
        self.temperature = float(temperature)

    def generate(self, *, system_prompt: str, context_chunks: list[dict], user_question: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set. Set it to use OpenAI chat completions.")

        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)

        facts_lines: list[str] = []
        for idx, ch in enumerate(context_chunks, start=1):
            file_path = ch.get("file_path") or (ch.get("metadata") or {}).get("file_path") or ""
            text = ch.get("text") or ""
            facts_lines.append(f'{idx}) [{file_path}] {text}')

        user_content = (
            f"\"Вопрос гостя: {user_question}\"\n\n"
            "\"ФАКТЫ ИЗ БАЗЫ (используй только их):\"\n"
            + "\n".join(facts_lines)
            + "\n\n"
            "\"Правила:\n"
            "- если ответа нет в фактах — скажи, что лучше уточнить у администратора/отдела праздников и дай контакт из базы\n"
            "- не выдумывай\n"
            "- не упоминай, что ты ИИ/бот\""
        )

        resp = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        msg = resp.choices[0].message
        return (msg.content or "").strip()
