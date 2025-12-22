from __future__ import annotations

import random
import re
import time
from typing import Optional

# TODO: Add real Telegram sticker file_id values here later.
sticker_id_map: dict[str, str] = {}

_last_sent_at: dict[int, float] = {}
_msgs_since_last: dict[int, int] = {}


def _can_send(user_id: int) -> bool:
    msgs_ok = _msgs_since_last.get(user_id, 0) >= 8
    last = _last_sent_at.get(user_id, 0.0)
    time_ok = (time.time() - last) >= 180
    return msgs_ok and time_ok


def should_send_sticker(text: str, user_id: int) -> Optional[str]:
    t = (text or "").lower()
    _msgs_since_last[user_id] = _msgs_since_last.get(user_id, 0) + 1

    if not _can_send(user_id):
        return None

    if re.search(r"\b(спасибо|круто|класс)\b", t) and random.random() < 0.30:
        _last_sent_at[user_id] = time.time()
        _msgs_since_last[user_id] = 0
        return "happy"

    if re.search(r"\b(не работает|блин|плохо)\b", t) and random.random() < 0.20:
        _last_sent_at[user_id] = time.time()
        _msgs_since_last[user_id] = 0
        return "support"

    if re.search(r"\b(день рождения|праздник|др)\b", t) and random.random() < 0.15:
        _last_sent_at[user_id] = time.time()
        _msgs_since_last[user_id] = 0
        return "party"

    return None
