"""
Unified intent detection for JuCity AI Manager.

This module provides a single source of truth for intent classification,
used by both the API (app) and Telegram bot.
"""
from __future__ import annotations

import re


# Intent keywords mapping - ordered by priority (more specific first)
INTENT_KEYWORDS: dict[str, list[str]] = {
    # Park facts - размер, площадь, аттракционы (количество)
    "park_facts": [
        "размер", "площад", "кв", "м²", "метр",
        "сколько аттракцион", "40", "большой парк", "маленький парк",
    ],
    # Socks - носки, сменка
    "socks": [
        "носки", "носок", "в носках", "купить носки",
        "без носков", "сменка", "сменная обувь",
    ],
    # Attractions - аттракционы, развлечения
    "attractions": [
        "аттракционы", "что есть", "какие есть",
        "батут", "горки", "карусели", "лабиринт", "развлечения",
    ],
    # Contacts
    "contacts": [
        "контакт", "телефон", "позвон", "звон", "email", "почт",
    ],
    # Location
    "location": [
        "адрес", "как добраться", "где находится", "локаци",
    ],
    # Rules
    "rules": [
        "правил", "запрещен",
    ],
    # Graduation
    "graduation": [
        "выпускн",
    ],
    # Birthday / parties
    "birthday": [
        "день рождения", "праздник", "банкет", "комната", "анимация",
    ],
    # Hours
    "hours": [
        "1 января", "31 декабря", "до скольки", "режим", "работаете",
    ],
    # Discounts
    "discounts": [
        "скидк", "льгот", "овз", "многодет",
    ],
    # VR
    "vr": [
        "vr",
    ],
    # Phygital
    "phygital": [
        "фиджитал",
    ],
    # Own food / cake
    "own_food_rules": [
        "торт", "сладкий",
    ],
    # Online tickets
    "tickets_online": [
        "купить билет онлайн", "на сайте купить билет",
        "оплатить на сайте", "онлайн билет", "прям на сайте",
    ],
    # Prices - last because it's the broadest
    "prices": [
        "сколько стоит", "цена", "билет",
        "понедельник", "вторник", "сред", "четверг",
        "пятниц", "суббот", "воскрес",
    ],
}

# Intent hints used by bot to determine if context should be applied
INTENT_HINTS: tuple[str, ...] = (
    "1 января", "31 декабря", "до скольки", "режим", "работаете",
    "скидк", "льгот", "овз", "многодет", "vr", "фиджитал",
    "торт", "сладкий", "купить билет онлайн", "на сайте купить билет",
    "оплатить на сайте", "онлайн билет", "прям на сайте",
    "сколько стоит", "цена", "билет",
    "понедельник", "вторник", "сред", "четверг", "пятниц", "суббот", "воскрес",
    "носки", "носок", "сменка", "сменная обувь",
    "размер", "площад", "кв", "м²", "метр",
    "аттракционы", "что есть", "какие есть", "батут", "горки", "карусели", "лабиринт", "развлечения",
    "адрес", "как добраться", "контакт", "телефон", "правил",
    "выпускн", "день рождения", "праздник", "банкет", "комната", "анимация",
)

# Context hints for continuing a topic
LAST_TOPIC_CONTEXT: dict[str, str] = {
    "prices": "Контекст: обсуждаем цену билета.",
    "discounts": "Контекст: обсуждаем скидки и льготы.",
    "hours": "Контекст: обсуждаем режим работы парка.",
    "location": "Контекст: обсуждаем адрес и как добраться.",
    "rules": "Контекст: обсуждаем правила посещения.",
    "birthday": "Контекст: обсуждаем день рождения в парке.",
    "graduation": "Контекст: обсуждаем выпускные в парке.",
    "vr": "Контекст: обсуждаем VR в парке.",
    "phygital": "Контекст: обсуждаем фиджитал в парке.",
    "contacts": "Контекст: обсуждаем контакты парка.",
    "tickets_online": "Контекст: обсуждаем покупку билета онлайн.",
    "park_facts": "Контекст: обсуждаем размер парка.",
    "attractions": "Контекст: обсуждаем аттракционы и развлечения.",
    "socks": "Контекст: обсуждаем правила про носки.",
    "own_food_rules": "Контекст: обсуждаем правила про еду и торт.",
    "cake_fee": "Контекст: обсуждаем сладкий сбор за торт на празднике.",
}

# Booking triggers
BOOKING_TRIGGERS: tuple[str, ...] = (
    "забронировать", "бронь", "заказать",
    "хочу праздник", "день рождения", "выпускной", "анимация",
)

# Party keywords for detecting party-related context
PARTY_KEYWORDS: tuple[str, ...] = (
    "день рождения", "праздник", "выпускной", "анимация",
    "бронь", "комната", "банкет", "торт",
)

# Other topic triggers (to check if switching context)
OTHER_TOPIC_TRIGGERS: tuple[str, ...] = (
    "сколько стоит", "цена", "билет", "скидк", "льгот", "овз", "многодет",
    "режим", "до скольки", "работаете", "адрес", "как добраться",
    "контакт", "vr", "фиджитал",
)


def detect_intent(question: str) -> str:
    """
    Detect user intent from question text.
    
    Returns intent string or 'general' if no specific intent detected.
    """
    q = question.lower()
    
    # Special case: regex for "др" (birthday abbreviation)
    if re.search(r"\bдр\b", q):
        return "birthday"
    
    # Check each intent in priority order
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in q:
                return intent
    
    return "general"


def has_intent_hints(text: str) -> bool:
    """Check if text contains any intent-specific keywords."""
    t = (text or "").lower()
    if re.search(r"\bдр\b", t):
        return True
    return any(hint in t for hint in INTENT_HINTS)


def has_party_keywords(texts: list[str]) -> bool:
    """Check if any text in list contains party-related keywords."""
    for t in texts:
        low = (t or "").lower()
        if any(key in low for key in PARTY_KEYWORDS):
            return True
        if re.search(r"\bдр\b", low):
            return True
    return False


def has_booking_triggers(text: str) -> bool:
    """Check if text contains booking request triggers."""
    t = (text or "").lower()
    return any(trigger in t for trigger in BOOKING_TRIGGERS)


def should_contextualize_cake_fee(text: str, last_topic: str | None) -> bool:
    """Check if cake fee question should be contextualized."""
    if last_topic not in ("cake_fee", "birthday", "own_food_rules"):
        return False
    t = (text or "").lower()
    if not any(trigger in t for trigger in ("1000", "за что", "почему")):
        return False
    if any(trigger in t for trigger in OTHER_TOPIC_TRIGGERS):
        return False
    return True


def get_context_hint(last_topic: str | None) -> str | None:
    """Get context hint for a topic."""
    if not last_topic:
        return None
    return LAST_TOPIC_CONTEXT.get(last_topic)
