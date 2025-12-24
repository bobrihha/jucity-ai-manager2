from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import aiosqlite

PROFILE_TTL_DAYS = 365
_SECONDS_IN_DAY = 60 * 60 * 24


def _empty_profile() -> dict[str, Any]:
    return {
        "name": None,
        "kids": [],
        "visit_date": None,
        "preferences": {"likes": [], "notes": []},
        "last_park": "nn",
    }


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def _is_expired(updated_ts: int) -> bool:
    ttl_seconds = PROFILE_TTL_DAYS * _SECONDS_IN_DAY
    return int(time.time()) - int(updated_ts) > ttl_seconds


class MemoryStore:
    def __init__(self, db_path: str = "data/bot_memory.sqlite3") -> None:
        self.db_path = db_path
        self._initialized = False

    async def init(self) -> None:
        if self._initialized:
            return

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profile (
                    user_id INTEGER PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    last_topic TEXT,
                    history_json TEXT,
                    updated_ts INTEGER NOT NULL
                )
                """
            )
            # Add columns if they don't exist (migration for existing DBs)
            try:
                await db.execute("ALTER TABLE user_profile ADD COLUMN last_topic TEXT")
            except Exception:
                pass  # Column already exists
            try:
                await db.execute("ALTER TABLE user_profile ADD COLUMN history_json TEXT")
            except Exception:
                pass  # Column already exists
            await db.commit()
        self._initialized = True

    async def get_profile(self, user_id: int) -> dict[str, Any]:
        await self.init()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT data_json, updated_ts FROM user_profile WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return _empty_profile()

        data_json, updated_ts = row
        if _is_expired(int(updated_ts)):
            await self._delete_profile(user_id)
            return _empty_profile()

        try:
            data = json.loads(data_json)
        except json.JSONDecodeError:
            data = {}

        base = _empty_profile()
        if isinstance(data, dict):
            return _deep_merge(base, data)
        return base

    async def upsert_profile(self, user_id: int, patch: dict[str, Any]) -> dict[str, Any]:
        await self.init()

        current = await self.get_profile(user_id)
        updated = _deep_merge(current, patch)
        payload = json.dumps(updated, ensure_ascii=False)
        now_ts = int(time.time())

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO user_profile (user_id, data_json, updated_ts)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    data_json = excluded.data_json,
                    updated_ts = excluded.updated_ts
                """,
                (user_id, payload, now_ts),
            )
            await db.commit()

        return updated

    async def get_context(self, user_id: int) -> dict[str, Any]:
        """Get session context (last_topic and history) for a user."""
        await self.init()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT last_topic, history_json, updated_ts FROM user_profile WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return {"last_topic": None, "history": []}

        last_topic, history_json, updated_ts = row
        
        # Check expiration
        if _is_expired(int(updated_ts)):
            return {"last_topic": None, "history": []}

        history = []
        if history_json:
            try:
                history = json.loads(history_json)
            except json.JSONDecodeError:
                history = []

        return {"last_topic": last_topic, "history": history if isinstance(history, list) else []}

    async def update_context(
        self,
        user_id: int,
        *,
        last_topic: str | None = None,
        history: list[str] | None = None,
    ) -> None:
        """Update session context (last_topic and/or history) for a user."""
        await self.init()

        now_ts = int(time.time())
        history_json = json.dumps(history, ensure_ascii=False) if history is not None else None

        async with aiosqlite.connect(self.db_path) as db:
            # Check if user exists
            async with db.execute(
                "SELECT user_id FROM user_profile WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                exists = await cursor.fetchone()

            if exists:
                # Build dynamic update
                updates = ["updated_ts = ?"]
                params: list[Any] = [now_ts]
                
                if last_topic is not None:
                    updates.append("last_topic = ?")
                    params.append(last_topic)
                if history_json is not None:
                    updates.append("history_json = ?")
                    params.append(history_json)
                
                params.append(user_id)
                await db.execute(
                    f"UPDATE user_profile SET {', '.join(updates)} WHERE user_id = ?",
                    params,
                )
            else:
                # Insert new row
                await db.execute(
                    """
                    INSERT INTO user_profile (user_id, data_json, last_topic, history_json, updated_ts)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, json.dumps(_empty_profile(), ensure_ascii=False), last_topic, history_json, now_ts),
                )
            await db.commit()

    async def touch(self, user_id: int) -> None:
        await self.init()
        now_ts = int(time.time())

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT data_json FROM user_profile WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()

            if row:
                await db.execute(
                    "UPDATE user_profile SET updated_ts = ? WHERE user_id = ?",
                    (now_ts, user_id),
                )
            else:
                payload = json.dumps(_empty_profile(), ensure_ascii=False)
                await db.execute(
                    "INSERT INTO user_profile (user_id, data_json, updated_ts) VALUES (?, ?, ?)",
                    (user_id, payload, now_ts),
                )
            await db.commit()

    async def _delete_profile(self, user_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM user_profile WHERE user_id = ?", (user_id,))
            await db.commit()

