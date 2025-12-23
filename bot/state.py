from __future__ import annotations

from typing import Any

from aiogram.fsm.state import State, StatesGroup

user_ctx: dict[int, dict[str, Any]] = {}


def get_user_ctx(user_id: int) -> dict[str, Any]:
    ctx = user_ctx.get(user_id)
    if ctx is None:
        ctx = {"last_topic": None, "history": []}
        user_ctx[user_id] = ctx
    return ctx


def append_history(user_id: int, text: str, limit: int = 6) -> list[str]:
    ctx = get_user_ctx(user_id)
    history = ctx.get("history")
    if not isinstance(history, list):
        history = []
    history.append(text)
    if len(history) > limit:
        history = history[-limit:]
    ctx["history"] = history
    return history


def get_history(user_id: int, limit: int = 6) -> list[str]:
    ctx = get_user_ctx(user_id)
    history = ctx.get("history")
    if not isinstance(history, list):
        return []
    return history[-limit:]


class UserState(StatesGroup):
    park = State()
