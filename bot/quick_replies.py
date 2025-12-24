from __future__ import annotations

from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parents[1]

# Map menu topics to KB files.
TOPIC_FILES: dict[str, str] = {
    "prices": "kb/nn/tickets/prices.md",
    "discounts": "kb/nn/tickets/discounts.md",
    "birthday": "kb/nn/parties/birthday.md",
    "graduation": "kb/nn/parties/graduation.md",
    "hours": "kb/nn/core/hours.md",
    "location": "kb/nn/core/location.md",
    "rules": "kb/nn/rules/visit_rules.md",
    "vr": "kb/nn/services/vr.md",
    "phygital": "kb/nn/services/phygital.md",
    "contacts": "kb/nn/core/contacts.md",
}


def _extract_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^{re.escape(heading)}\s*$", flags=re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", text[start:], flags=re.MULTILINE)
    end = start + next_match.start() if next_match else len(text)
    return text[start:end].strip()


def _build_reply_from_kb(file_path: str) -> str:
    path = BASE_DIR / file_path
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    if not text:
        return ""

    facts = _extract_section(text, "## Факты")
    how = _extract_section(text, "## Как объяснять гостю")

    parts: list[str] = []
    if facts:
        parts.append(facts)
    if how:
        parts.append(how)

    if not parts:
        return text
    return "\n\n".join(parts)


def build_quick_replies() -> dict[str, str]:
    templates: dict[str, str] = {}
    for topic, file_path in TOPIC_FILES.items():
        reply = _build_reply_from_kb(file_path)
        if reply:
            templates[topic] = reply
    return templates


# Auto-synced quick replies from KB.
TOPIC_TEMPLATES = build_quick_replies()
