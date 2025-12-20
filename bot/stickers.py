from __future__ import annotations

import time


class StickerPolicy:
    def __init__(self, *, min_seconds_between: int = 90) -> None:
        self.min_seconds_between = min_seconds_between
        self._last_sent_at: dict[int, float] = {}

    def should_send(self, user_id: int, *, kind: str) -> bool:
        # Minimal, conservative policy: stickers are optional and rare.
        # We keep it off by default until sticker IDs are configured.
        return False

    def mark_sent(self, user_id: int) -> None:
        self._last_sent_at[user_id] = time.time()


# Placeholder: add real sticker file_ids here later if needed.
STICKERS: dict[str, str] = {}

