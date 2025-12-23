from __future__ import annotations

import re
from typing import Any


_NAME_PATTERNS = [
    re.compile(r"\bменя\s+зовут\s+([A-Za-zА-Яа-яЁё]{2,20})\b", re.IGNORECASE),
    re.compile(r"\bя\s+([A-Za-zА-Яа-яЁё]{2,20})\b", re.IGNORECASE),
    re.compile(r"\bэто\s+([A-Za-zА-Яа-яЁё]{2,20})\b", re.IGNORECASE),
]

_NAME_STOPWORDS = {
    "из",
    "в",
    "на",
    "не",
    "у",
    "за",
    "по",
    "что",
    "как",
    "могу",
    "хочу",
    "буду",
    "иду",
    "пишу",
    "спрошу",
    "знаю",
    "понимаю",
    "просто",
    "тут",
    "здесь",
}


_AGE_PATTERNS = [
    re.compile(r"\bреб[её]нк[ау]\s+(\d{1,2})\b", re.IGNORECASE),
    re.compile(r"\bреб[её]нк[ау]\s+(\d{1,2})\s*лет\b", re.IGNORECASE),
    re.compile(r"\bдочк[ае]\s+(\d{1,2})\b", re.IGNORECASE),
    re.compile(r"\bсыну\s+(\d{1,2})\b", re.IGNORECASE),
]


_KID_NAME_PATTERNS = [
    re.compile(r"\bдочк[ае]\s+([A-Za-zА-Яа-яЁё]{2,20})\b", re.IGNORECASE),
    re.compile(r"\bсын\s+([A-Za-zА-Яа-яЁё]{2,20})\b", re.IGNORECASE),
]


_CHILDREN_LIST_RE = re.compile(r"\bдети\s*[:\-]\s*([^\n]+)", re.IGNORECASE)
_CHILD_NAME_AGE_RE = re.compile(r"([A-Za-zА-Яа-яЁё]{2,20})\s+(\d{1,2})")


_VISIT_PATTERNS = [
    re.compile(r"\bзавтра\b", re.IGNORECASE),
    re.compile(r"\bв\s+субботу\b", re.IGNORECASE),
    re.compile(r"\b31\s*декабря\b", re.IGNORECASE),
    re.compile(r"\b1\s*января\b", re.IGNORECASE),
    re.compile(r"\bна\s+выходных\b", re.IGNORECASE),
]


def extract_profile_patch(text: str) -> dict[str, Any]:
    if not text:
        return {}

    patch: dict[str, Any] = {}

    name = _extract_name(text)
    if name:
        patch["name"] = name

    kids = _extract_kids(text)
    if kids:
        patch["kids"] = kids

    visit_date = _extract_visit_date(text)
    if visit_date:
        patch["visit_date"] = visit_date

    likes = _extract_likes(text)
    if likes:
        patch["preferences"] = {"likes": likes}

    return patch


def _extract_name(text: str) -> str | None:
    for pattern in _NAME_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        candidate = m.group(1).strip()
        if candidate.lower() in _NAME_STOPWORDS:
            continue
        return candidate
    return None


def _extract_kids(text: str) -> list[dict[str, Any]]:
    kids: list[dict[str, Any]] = []
    seen: set[tuple[str | None, int | None]] = set()

    list_match = _CHILDREN_LIST_RE.search(text)
    if list_match:
        raw = list_match.group(1)
        for name, age in _CHILD_NAME_AGE_RE.findall(raw):
            entry = {"name": name, "age": int(age)}
            key = (name.lower(), int(age))
            if key not in seen:
                seen.add(key)
                kids.append(entry)

    for pattern in _KID_NAME_PATTERNS:
        for match in pattern.findall(text):
            name = match.strip()
            key = (name.lower(), None)
            if key not in seen:
                seen.add(key)
                kids.append({"name": name})

    for pattern in _AGE_PATTERNS:
        for match in pattern.findall(text):
            try:
                age = int(match)
            except ValueError:
                continue
            key = (None, age)
            if key not in seen:
                seen.add(key)
                kids.append({"age": age})

    return kids


def _extract_visit_date(text: str) -> str | None:
    for pattern in _VISIT_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None


def _extract_likes(text: str) -> list[str]:
    if re.search(r"\bбатут\w*\b", text, flags=re.IGNORECASE):
        return ["батуты"]
    return []
