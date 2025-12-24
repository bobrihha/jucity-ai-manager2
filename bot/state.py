"""
User context management with in-memory cache and SQLite persistence.

The context is kept in memory for fast access during the session,
and periodically synced to SQLite for persistence across restarts.
"""
from __future__ import annotations

from typing import Any

# In-memory cache for quick access during session
_user_ctx: dict[int, dict[str, Any]] = {}


def get_user_ctx(user_id: int) -> dict[str, Any]:
    """
    Get or create user context from in-memory cache.
    
    Call load_user_ctx_from_db() at session start to populate from DB.
    """
    ctx = _user_ctx.get(user_id)
    if ctx is None:
        ctx = {"last_topic": None, "history": []}
        _user_ctx[user_id] = ctx
    return ctx


def set_user_ctx(user_id: int, ctx: dict[str, Any]) -> None:
    """Set user context in memory (used when loading from DB)."""
    _user_ctx[user_id] = ctx


def append_history(user_id: int, text: str, limit: int = 6) -> list[str]:
    """Append to history and return updated history list."""
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
    """Get history from in-memory context."""
    ctx = get_user_ctx(user_id)
    history = ctx.get("history")
    if not isinstance(history, list):
        return []
    return history[-limit:]


def clear_user_ctx(user_id: int) -> None:
    """Clear user context from memory."""
    if user_id in _user_ctx:
        del _user_ctx[user_id]


# Note: UserState removed as it was unused.
# If FSM states are needed in the future, add them back.
