from __future__ import annotations

import asyncio
import logging
import time

import httpx
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from bot.config import get_settings
from bot.keyboards import menu_button_kb, menu_inline_kb
from bot.quick_replies import TOPIC_TEMPLATES
from bot.memory_store import MemoryStore
from bot.profile_extractor import extract_profile_patch
from bot.state import append_history, get_user_ctx, set_user_ctx
from bot.stickers import should_send_sticker, sticker_id_map
from bot.utils_render import render_telegram_html
from shared.intents import (
    BOOKING_TRIGGERS,
    LAST_TOPIC_CONTEXT,
    PARTY_KEYWORDS,
    get_context_hint,
    has_booking_triggers,
    has_intent_hints,
    has_party_keywords,
    should_contextualize_cake_fee,
)


router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()

memory_store = MemoryStore()

API_BASE = settings.api_base_url.rstrip("/")

_HEALTH_TTL = 60.0
_health_cache = {"ok": None, "ts": 0.0, "build_id": None}

FALLBACK_ERROR = (
    "Ой, у меня временно не получается получить информацию 😕\n"
    "Можно уточнить по телефону парка: +7 (831) 213-50-50\n"
    "Или попробуйте повторить вопрос через минуту."
)

DATABASE_INFO_REPLY = (
    "Я отвечаю по базе знаний парка — это справочная информация (цены, правила, режим, услуги).\n"
    "Иногда бывает техническая пауза, и тогда я предлагаю телефон ресепшн."
)

TOPIC_QUESTIONS = {
    "prices": "Сколько стоит билет в будний день и в выходной? Есть ли ограничения по времени?",
    "discounts": "Какие скидки есть: ОВЗ, многодетные, СВО, 14–18 лет, пенсионеры, после 20:00?",
    "birthday": "Как проходит день рождения: условия, комнаты, время, что входит, можно ли торт?",
    "graduation": "Как проходят выпускные: условия, программа, длительность, как забронировать?",
    "hours": "Режим работы парка. Есть ли особые даты (31.12, 01.01)?",
    "location": "Адрес и как добраться до парка (Нижний Новгород).",
    "rules": "Какие правила посещения: носки, еда/напитки, возраст, сопровождение?",
    "vr": "VR входит в билет? Какие условия и где посмотреть цены?",
    "phygital": "Фиджитал входит в билет? Сколько стоит и как работает?",
    "contacts": "Контакты парка и отдела праздников.",
    "socks": "Можно ли у вас купить носки? И можно ли заходить в игровых зонах в обуви?",
}


# _LAST_TOPIC_CONTEXT moved to shared.intents.LAST_TOPIC_CONTEXT

# _INTENT_HINTS, BOOKING_TRIGGERS, _PARTY_KEYWORDS, _OTHER_TOPIC_TRIGGERS
# moved to shared.intents

_booking_hint_last: dict[int, float] = {}

_CAKE_FEE_SOURCES = {"kb/nn/food/own_food_rules.md"}

# Track which users have loaded context from DB
_loaded_from_db: set[int] = set()


async def _ensure_context_loaded(user_id: int) -> None:
    """Load user context from DB into memory cache if not already loaded."""
    if user_id in _loaded_from_db:
        return
    
    db_ctx = await memory_store.get_context(user_id)
    set_user_ctx(user_id, db_ctx)
    _loaded_from_db.add(user_id)

async def _update_last_topic(user_id: int, sources: list[str]) -> None:
    """Update last_topic based on response sources. Also saves to DB."""
    if not sources:
        return

    ctx = get_user_ctx(user_id)
    new_topic: str | None = None

    if "kb/nn/food/own_food_rules.md" in sources:
        new_topic = "cake_fee"
    elif "kb/nn/tickets/prices.md" in sources:
        new_topic = "prices"
    elif "kb/nn/tickets/discounts.md" in sources:
        new_topic = "discounts"
    elif "kb/nn/core/hours.md" in sources:
        new_topic = "hours"
    elif "kb/nn/core/location.md" in sources:
        new_topic = "location"
    elif "kb/nn/core/contacts.md" in sources:
        new_topic = "contacts"
    elif "kb/nn/rules/visit_rules.md" in sources:
        new_topic = "rules"
    elif "kb/nn/parties/birthday.md" in sources:
        new_topic = "birthday"
    elif "kb/nn/parties/graduation.md" in sources:
        new_topic = "graduation"
    elif "kb/nn/services/vr.md" in sources:
        new_topic = "vr"
    elif "kb/nn/services/phygital.md" in sources:
        new_topic = "phygital"
    elif "kb/nn/tickets/buy_online.md" in sources:
        new_topic = "tickets_online"
    elif "kb/nn/rules/socks.md" in sources:
        new_topic = "socks"
    elif "kb/nn/core/park_facts.md" in sources:
        new_topic = "park_facts"
    elif "kb/nn/park/attractions_overview.md" in sources:
        new_topic = "attractions"

    if new_topic:
        ctx["last_topic"] = new_topic
        # Persist to DB
        await memory_store.update_context(user_id, last_topic=new_topic)

# _should_contextualize_cake_fee, _has_intent_hints, _has_party_keywords
# moved to shared.intents


def _maybe_strip_party_contact(answer: str, user_text: str, history: list[str] | None) -> str:
    if not answer:
        return answer
    low_answer = answer.lower()
    if (
        "+7 962 509 74 93" not in answer
        and "+7 962 509-74-93" not in answer
        and "отдел праздников" not in low_answer
    ):
        return answer

    recent = []
    if history:
        recent = history[-2:]
    if user_text:
        recent.append(user_text)
    if has_party_keywords(recent):
        return answer

    triggers = ("если ты планируешь праздник", "лучше всего связаться")
    paragraphs = answer.split("\n\n")
    cut_idx = None
    for i, para in enumerate(paragraphs):
        low = para.lower()
        if any(t in low for t in triggers):
            cut_idx = i
            break

    if cut_idx is None:
        return answer

    kept = [p for p in paragraphs[:cut_idx] if p.strip()]
    base = "\n\n".join(kept).strip()
    tail = "Если захотите организовать праздник — скажите, подскажу контакты 😊"
    if base:
        return f"{base}\n\n{tail}"
    return tail


def _is_database_question(text: str) -> bool:
    t = (text or "").lower()
    return ("с какой базой" in t) or ("какая база" in t) or ("какую базу" in t)


def _should_send_booking_hint(text: str, user_id: int) -> bool:
    t = (text or "").lower()
    if not any(trigger in t for trigger in BOOKING_TRIGGERS):
        return False

    now = time.time()
    last = _booking_hint_last.get(user_id, 0.0)
    if (now - last) < 600:
        return False

    _booking_hint_last[user_id] = now
    return True


async def ensure_api_health() -> bool:
    now = time.time()
    cached_ok = _health_cache.get("ok")
    cached_ts = float(_health_cache.get("ts") or 0.0)
    if cached_ok is not None and (now - cached_ts) < _HEALTH_TTL:
        return bool(cached_ok)

    timeout = httpx.Timeout(2.0, connect=2.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(f"{API_BASE}/health")
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            _health_cache["ok"] = False
            _health_cache["build_id"] = None
            _health_cache["ts"] = time.time()
            return False

    if resp.status_code != 200:
        _health_cache["ok"] = False
        _health_cache["build_id"] = None
        _health_cache["ts"] = time.time()
        return False
    try:
        data = resp.json()
    except Exception:
        _health_cache["ok"] = False
        _health_cache["build_id"] = None
        _health_cache["ts"] = time.time()
        return False
    ok = data.get("status") == "ok"
    _health_cache["ok"] = ok
    _health_cache["build_id"] = data.get("build_id")
    _health_cache["ts"] = time.time()
    return bool(ok)


async def _ask_api(
    question: str,
    *,
    history: list[str] | None = None,
    profile: dict | None = None,
) -> dict:
    timeout = httpx.Timeout(connect=3.0, read=12.0, write=6.0, pool=6.0)
    backoffs = [0.4, 0.8]

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(2):
            try:
                resp = await client.post(
                    f"{API_BASE}/ask",
                    json={"question": question, "history": history, "profile": profile},
                )
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                logger.exception("ask_api error on attempt %s", attempt + 1, exc_info=exc)
                if attempt == 0:
                    await asyncio.sleep(backoffs[0])
                    continue
                return {"ok": False, "error": "ask_failed"}
            except Exception as exc:
                logger.exception("ask_api unexpected error on attempt %s", attempt + 1, exc_info=exc)
                return {"ok": False, "error": "ask_failed"}

            if resp.status_code != 200:
                logger.error("ask_api status=%s", resp.status_code)
                return {"ok": False, "error": "ask_failed", "status": resp.status_code}

            try:
                data = resp.json()
            except Exception as exc:
                logger.exception("ask_api json error on attempt %s", attempt + 1, exc_info=exc)
                return {"ok": False, "error": "ask_failed", "status": resp.status_code}

            return {"ok": True, "data": data}

    return {"ok": False, "error": "ask_failed"}


async def _maybe_send_sticker(message: Message, text: str) -> None:
    if not message.from_user:
        return

    sticker_key = should_send_sticker(text, message.from_user.id)
    if not sticker_key:
        return

    if sticker_key in sticker_id_map:
        # TODO: send_sticker(sticker_id_map[sticker_key])
        # await message.answer_sticker(sticker_id_map[sticker_key])
        pass


async def _send_long_message(message: Message, text: str, *, keyboard=None) -> None:
    if not text:
        return

    parts = text.split("\n\n")
    buffer = ""
    chunks: list[str] = []

    for part in parts:
        if not part.strip():
            continue
        candidate = part if not buffer else f"{buffer}\n\n{part}"
        if len(candidate) > 3500 and buffer:
            chunks.append(buffer)
            buffer = part
        else:
            buffer = candidate

    if buffer:
        chunks.append(buffer)

    for idx, chunk in enumerate(chunks):
        rendered = render_telegram_html(chunk)
        await message.answer(
            rendered,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=keyboard if idx == len(chunks) - 1 else None,
        )


async def _build_request_payload(user_id: int, user_text: str) -> tuple[list[str], dict]:
    history_short = append_history(user_id, user_text)
    # Persist history to DB
    await memory_store.update_context(user_id, history=history_short)
    
    patch = extract_profile_patch(user_text)
    if patch:
        await memory_store.upsert_profile(user_id, patch)
    profile = await memory_store.get_profile(user_id)
    return history_short, profile


async def _reply_with_answer(
    message: Message,
    question: str,
    *,
    user_id: int | None = None,
    history: list[str] | None = None,
    profile: dict | None = None,
    user_text: str | None = None,
) -> None:
    result = await _ask_api(question, history=history, profile=profile)
    if not result.get("ok"):
        health_ok = await ensure_api_health()
        if health_ok:
            await _send_long_message(
                message,
                "Что-то пошло не так, попробуйте повторить вопрос через минуту.",
                keyboard=menu_button_kb(),
            )
        else:
            await _send_long_message(message, FALLBACK_ERROR, keyboard=menu_button_kb())
        return

    data = result.get("data") or {}
    answer = str(data.get("answer") or "").strip()
    answer = _maybe_strip_party_contact(answer, user_text or question, history)
    sources = data.get("sources") or []

    effective_user_id = user_id
    if effective_user_id is None and message.from_user:
        effective_user_id = message.from_user.id

    if effective_user_id is not None:
        await _update_last_topic(effective_user_id, sources)
        logger.info("user_id=%s question=%r sources=%s", effective_user_id, question, sources)
    else:
        logger.info("user_id=unknown question=%r sources=%s", question, sources)

    if not answer:
        await _send_long_message(message, FALLBACK_ERROR, keyboard=menu_button_kb())
        return

    await _send_long_message(message, answer, keyboard=menu_button_kb())


async def _handle_topic(message: Message, topic: str, *, user_id: int | None = None) -> None:
    question = TOPIC_QUESTIONS.get(topic)
    if not question:
        await _send_long_message(
            message,
            "Не нашёл эту тему. Выберите из меню.",
            keyboard=menu_inline_kb(),
        )
        return
    template = TOPIC_TEMPLATES.get(topic)
    if template:
        if user_id is not None:
            await _ensure_context_loaded(user_id)
            history_short = append_history(user_id, question)
            ctx = get_user_ctx(user_id)
            ctx["last_topic"] = topic
            # Also save to DB (last_topic + history)
            await memory_store.update_context(user_id, last_topic=topic, history=history_short)
        await _send_long_message(message, template, keyboard=menu_button_kb())
        await _maybe_send_sticker(message, question)
        return
    history = None
    profile = None
    if user_id is not None:
        history, profile = await _build_request_payload(user_id, question)
    await _reply_with_answer(
        message,
        question,
        user_id=user_id,
        history=history,
        profile=profile,
        user_text=question,
    )
    await _maybe_send_sticker(message, question)


@router.message(CommandStart())
async def start(message: Message) -> None:
    text = (
        "Привет! Я Джуси из Джунгли Сити (Нижний Новгород) 😊\n"
        "Можно просто написать вопрос (как в обычном чате) —\n"
        "а кнопки ниже — для быстрого выбора темы."
    )
    await _send_long_message(message, text, keyboard=menu_inline_kb())
    await _send_long_message(message, "Джунгли Сити Нижний Новгород", keyboard=ReplyKeyboardRemove())

    ok = await ensure_api_health()
    build_id = _health_cache.get("build_id") or "unknown"
    await _send_long_message(message, f"Версия: {build_id}")
    if ok:
        await _send_long_message(message, "Я на связи!")
    else:
        await _send_long_message(
            message,
            "Я отвечаю, но сервис сейчас недоступен — лучше уточнить по телефону парка: +7 (831) 213-50-50.",
        )


@router.message(Command("menu"))
async def menu(message: Message) -> None:
    await _send_long_message(message, "Выберите тему 👇", keyboard=menu_inline_kb())
    ok = await ensure_api_health()
    if ok:
        await _send_long_message(message, "Я на связи!")
    else:
        await _send_long_message(
            message,
            "Я отвечаю, но сервис сейчас недоступен — лучше уточнить по телефону парка: +7 (831) 213-50-50.",
        )


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    text = (
        "Я подсказываю по парку: билеты, скидки, режим работы, правила, праздники и контакты.\n"
        "Можно написать вопрос или выбрать тему в меню ниже."
    )
    await _send_long_message(message, text, keyboard=menu_inline_kb())


@router.message(Command("prices"))
async def prices_cmd(message: Message) -> None:
    await _handle_topic(message, "prices", user_id=message.from_user.id if message.from_user else None)


@router.message(Command("discounts"))
async def discounts_cmd(message: Message) -> None:
    await _handle_topic(message, "discounts", user_id=message.from_user.id if message.from_user else None)


@router.message(Command("hours"))
async def hours_cmd(message: Message) -> None:
    await _handle_topic(message, "hours", user_id=message.from_user.id if message.from_user else None)


@router.callback_query(F.data == "menu")
async def menu_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await _send_long_message(
            callback.message,
            "Выберите тему 👇",
            keyboard=menu_inline_kb(),
        )


@router.callback_query(F.data.startswith("topic:"))
async def topic_callback(callback: CallbackQuery) -> None:
    if not callback.data:
        return

    _, topic = callback.data.split(":", 1)
    await callback.answer()

    if callback.message:
        await _handle_topic(callback.message, topic, user_id=callback.from_user.id)


@router.message()
async def any_text(message: Message) -> None:
    if not message.text:
        return

    question = message.text.strip()
    if not question:
        return

    if _is_database_question(question):
        await _send_long_message(message, DATABASE_INFO_REPLY, keyboard=menu_button_kb())
        return

    context_question = question
    history = None
    profile = None
    user_id = None
    if message.from_user:
        user_id = message.from_user.id
        await _ensure_context_loaded(user_id)
        history, profile = await _build_request_payload(user_id, question)
        ctx = get_user_ctx(user_id)
        last_topic = ctx.get("last_topic")
        if should_contextualize_cake_fee(question, last_topic):
            context_question = (
                "Контекст: обсуждаем сладкий сбор за торт на празднике. "
                f"Вопрос: {question}"
            )
        elif last_topic and not has_intent_hints(question):
            hint = get_context_hint(last_topic)
            if hint:
                context_question = f"{hint} Вопрос: {question}"

    await _reply_with_answer(
        message,
        context_question,
        user_id=user_id,
        history=history,
        profile=profile,
        user_text=question,
    )

    if message.from_user and _should_send_booking_hint(question, message.from_user.id):
        await _send_long_message(
            message,
            "Если хотите, могу сразу дать контакт отдела праздников для брони: +7 962 509-74-93",
        )

    await _maybe_send_sticker(message, question)
