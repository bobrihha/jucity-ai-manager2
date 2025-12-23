from __future__ import annotations

import html
import re


_PHONE_RE = re.compile(r"\+7[\s()\-]*\d{3}[\s()\-]*\d{3}[\s()\-]*\d{2}[\s()\-]*\d{2}")


def _normalize_phones(text: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) == 11 and digits.startswith("7"):
            return "+7" + digits[1:]
        if len(digits) == 10:
            return "+7" + digits
        return match.group(0)

    return _PHONE_RE.sub(_repl, text)


def render_telegram_html(text: str) -> str:
    if not text:
        return ""

    text = _normalize_phones(text)
    escaped = html.escape(text, quote=False)

    # Bold: **text** -> <b>text</b>
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped, flags=re.DOTALL)

    # Links: [text](https://...) -> <a href="https://...">text</a>
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        r"<a href=\"\2\">\1</a>",
        escaped,
    )

    return escaped
