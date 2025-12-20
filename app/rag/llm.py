from __future__ import annotations

from abc import ABC, abstractmethod


class LLM(ABC):
    @abstractmethod
    def generate(self, *, system_prompt: str, question: str, context: str) -> str: ...


class StubLLM(LLM):
    def generate(self, *, system_prompt: str, question: str, context: str) -> str:
        return (
            "Я могу подсказать по базе знаний Джунгли Сити (НН). "
            "Сейчас генерация ответа через LLM не подключена (TODO). "
            "Я нашёл релевантные источники — посмотрите их, и я помогу сформулировать ответ."
        )

