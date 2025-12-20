from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class StickerDecision:
    send: bool
    sticker_key: str


# TODO: Add real Telegram sticker file_id values here.
# Example:
# STICKER_FILE_ID_MAP = {
#   "joy": "CAACAgIAAxkBAA...",
#   "support": "CAACAgIAAxkBAA...",
#   "party": "CAACAgIAAxkBAA...",
# }
STICKER_FILE_ID_MAP: dict[str, str] = {}


def should_send_sticker(text: str) -> StickerDecision:
    t = (text or "").lower()

    thanks = bool(re.search(r"\b(спасибо|круто|отлично)\b", t))
    upset = bool(re.search(r"\b(плохо|не работает|блин)\b", t))
    party = bool(re.search(r"\b(день рождения|др|праздник|банкет|выпускн)\b", t))

    if thanks and random.random() < 0.30:
        return StickerDecision(send=True, sticker_key="joy")
    if upset and random.random() < 0.20:
        return StickerDecision(send=True, sticker_key="support")
    if party and random.random() < 0.15:
        return StickerDecision(send=True, sticker_key="party")

    return StickerDecision(send=False, sticker_key="")


class StickerPolicy:
    def __init__(self) -> None:
        self._last_sent_at: dict[int, float] = {}
        self._msgs_since_last: dict[int, int] = {}

    def record_user_message(self, user_id: int) -> None:
        self._msgs_since_last[user_id] = self._msgs_since_last.get(user_id, 0) + 1

    def can_send_now(self, user_id: int) -> bool:
        msgs_ok = self._msgs_since_last.get(user_id, 0) >= 8
        last = self._last_sent_at.get(user_id, 0.0)
        time_ok = (time.time() - last) >= 180
        return msgs_ok and time_ok

    def mark_sent(self, user_id: int) -> None:
        self._last_sent_at[user_id] = time.time()
        self._msgs_since_last[user_id] = 0


sticker_policy = StickerPolicy()
