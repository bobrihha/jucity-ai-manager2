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
from bot.memory_store import MemoryStore
from bot.profile_extractor import extract_profile_patch
from bot.state import append_history, get_user_ctx
from bot.stickers import should_send_sticker, sticker_id_map
from bot.utils_render import render_telegram_html


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

TOPIC_TEMPLATES = {
    "prices": """Билет в наш парк стоит:

- Понедельник: 990 ₽
- Вторник–пятница: 1190 ₽
- Суббота–воскресенье: 1590 ₽

Важно, что у нас нет ограничений по времени — дети могут играть весь день без перерыва! А взрослые 18+ проходят бесплатно. 😊

Если нужно — подскажу маршрут или контакты.""",
    "discounts": """Есть скидки: именинник 50% (день рождения +5 дней), многодетные 30% (кроме пн), 1–4 года 20% (вт–пт), после 20:00 50% (кроме пн), ОВЗ бесплатно (пн–пт), СВО 30% (пн–пт), 14–18 лет 50%, пенсионерам 20% (15.07–15.08).
Скажите, кто идёт и на какой день — подберу подходящую.""",
    "birthday": """День рождения у нас проходит очень весело! Есть два формата:

1. Зона ресторана — здесь вы можете отмечать без лимита по времени, выбирая удобное время.
2. Волшебная комната — даётся на 3 часа, с возможными слотами в 10:30, 14:30 и 18:30. Для этого нужно купить от 6 детских билетов, а именинник идёт бесплатно.

Что касается торта, вы можете принести свой, но нужно будет оплатить "сладкий сбор" в 1000 ₽. Это означает, что вы берёте на себя ответственность за качество торта. Свою еду и напитки приносить нельзя, но в нашем ресторане есть много вкусного!

Если хотите узнать больше о дате и количестве детей, я с удовольствием помогу подобрать лучший вариант! 😊""",
    "graduation": """Выпускные у нас проходят очень весело! Мы подбираем программу в зависимости от возраста и количества детей. Обычно это 60 минут шоу или анимации на выбор, плюс игры и активности. У нас есть разные программы, такие как “Мультяшкино”, “Туса-Джуса” и “Город профессий”. 🎉

Чтобы забронировать, лучше всего связаться с нашим отделом праздников по телефону +7 962 509 74 93. Условия и цены могут зависеть от сезона, так что лучше уточнить заранее.

Какую дату вы планируете для выпускного и сколько детей будет? Я помогу с вариантами! Просто напишите сообщение в чат 😊""",
    "hours": """Режим: пн 12:00–22:00, вт–вс 10:00–22:00. 31.12 до 18:00, 01.01 не работаем.
Если нужно — подскажу маршрут/контакты.""",
    "location": """Адрес: Нижний Новгород, ул. Коминтерна, 11, ТЦ «Лента», 1 этаж.
Парк внутри ТЦ, есть парковка. Если нужно — подскажу маршрут.""",
    "rules": """В нашем парке есть несколько важных правил для посещения:

1. В игровые зоны можно заходить только в носках. Уличная обувь оставляем за дверью. Если носков нет, их можно купить на месте.
2. В зоне ресторана можно быть в чистой сменной обуви, например, в тапочках.
3. Возрастных ограничений нет, но обязательно нужно сопровождение взрослых для детей.

Если есть еще вопросы или нужна помощь, просто напишите сообщение  в чат! 😊""",
    "vr": """VR — отдельная услуга, не входит в безлимит. Цены: https://nn.jucity.ru/tickets-vr/.
Можно купить на ресепшн во время визита.""",
    "phygital": """Фиджитал — это зона с интерактивными играми, где можно поиграть в сюжетные и спортивные игры, например, с динозаврами или в баскетбол. Билет на фиджитал приобретается отдельно и его можно купить на ресепшн, как сразу при покупке безлимита, так и в течение визита.

Стоимость и форматы зависят от актуального прайса, поэтому лучше уточнить это у администратора на месте. Если у вас есть еще вопросы, я с радостью помогу! 😊""",
    "contacts": """Вот контакты нашего парка и отдела праздников:

- Отдел праздников: +7 96250974 93
- Горячая линия: +7 (831) 213-50-50
- Доп. номер: +7 (963) 230-50-50
- Email праздников: prazdnik52@jucity.ru

Если у вас вопросы по бронированию или программам, лучше сразу обратиться в отдел праздников — они помогут быстрее! 😊 Чем могу помочь ещё? Просто напишите сообщение прямо здесь и я отвечу""",
}

_LAST_TOPIC_CONTEXT = {
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
}

_INTENT_HINTS = (
    "1 января",
    "31 декабря",
    "до скольки",
    "режим",
    "работаете",
    "скидк",
    "льгот",
    "овз",
    "многодет",
    "vr",
    "фиджитал",
    "торт",
    "сладкий",
    "купить билет онлайн",
    "на сайте купить билет",
    "оплатить на сайте",
    "онлайн билет",
    "прям на сайте",
    "сколько стоит",
    "цена",
    "билет",
    "понедельник",
    "вторник",
    "сред",
    "четверг",
    "пятниц",
    "суббот",
    "воскрес",
    "носки",
    "носок",
    "сменка",
    "сменная обувь",
    "размер",
    "площад",
    "кв",
    "м²",
    "метр",
    "аттракционы",
    "что есть",
    "какие есть",
    "батут",
    "горки",
    "карусели",
    "лабиринт",
    "развлечения",
    "адрес",
    "как добраться",
    "контакт",
    "телефон",
    "правил",
    "выпускн",
    "день рождения",
    "праздник",
    "банкет",
    "комната",
    "анимация",
)

BOOKING_TRIGGERS = (
    "забронировать",
    "бронь",
    "заказать",
    "хочу праздник",
    "день рождения",
    "выпускной",
    "анимация",
)

_booking_hint_last: dict[int, float] = {}

_CAKE_FEE_SOURCES = {"kb/nn/food/own_food_rules.md"}
_PARTY_KEYWORDS = (
    "день рождения",
    "праздник",
    "выпускной",
    "анимация",
    "бронь",
    "комната",
    "банкет",
    "торт",
)

_OTHER_TOPIC_TRIGGERS = (
    "сколько стоит",
    "цена",
    "билет",
    "скидк",
    "льгот",
    "овз",
    "многодет",
    "режим",
    "до скольки",
    "работаете",
    "адрес",
    "как добраться",
    "контакт",
    "vr",
    "фиджитал",
)

def _update_last_topic(user_id: int, sources: list[str]) -> None:
    if not sources:
        return

    ctx = get_user_ctx(user_id)

    if "kb/nn/food/own_food_rules.md" in sources:
        ctx["last_topic"] = "cake_fee"
        return
    if "kb/nn/tickets/prices.md" in sources:
        ctx["last_topic"] = "prices"
        return
    if "kb/nn/tickets/discounts.md" in sources:
        ctx["last_topic"] = "discounts"
        return
    if "kb/nn/core/hours.md" in sources:
        ctx["last_topic"] = "hours"
        return
    if "kb/nn/core/location.md" in sources:
        ctx["last_topic"] = "location"
        return
    if "kb/nn/core/contacts.md" in sources:
        ctx["last_topic"] = "contacts"
        return
    if "kb/nn/rules/visit_rules.md" in sources:
        ctx["last_topic"] = "rules"
        return
    if "kb/nn/parties/birthday.md" in sources:
        ctx["last_topic"] = "birthday"
        return
    if "kb/nn/parties/graduation.md" in sources:
        ctx["last_topic"] = "graduation"
        return
    if "kb/nn/services/vr.md" in sources:
        ctx["last_topic"] = "vr"
        return
    if "kb/nn/services/phygital.md" in sources:
        ctx["last_topic"] = "phygital"
        return
    if "kb/nn/tickets/buy_online.md" in sources:
        ctx["last_topic"] = "tickets_online"
        return
    if "kb/nn/rules/socks.md" in sources:
        ctx["last_topic"] = "socks"
        return
    if "kb/nn/core/park_facts.md" in sources:
        ctx["last_topic"] = "park_facts"
        return
    if "kb/nn/park/attractions_overview.md" in sources:
        ctx["last_topic"] = "attractions"
        return

def _should_contextualize_cake_fee(text: str, last_topic: str | None) -> bool:
    if last_topic not in ("cake_fee", "birthday"):
        return False
    t = (text or "").lower()
    if not any(trigger in t for trigger in ("1000", "за что", "почему")):
        return False
    if any(trigger in t for trigger in _OTHER_TOPIC_TRIGGERS):
        return False
    return True


def _has_intent_hints(text: str) -> bool:
    t = (text or "").lower()
    if re.search(r"\bдр\b", t):
        return True
    return any(hint in t for hint in _INTENT_HINTS)


def _has_party_keywords(texts: list[str]) -> bool:
    for t in texts:
        low = (t or "").lower()
        if any(key in low for key in _PARTY_KEYWORDS):
            return True
        if re.search(r"\bдр\b", low):
            return True
    return False


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
    if _has_party_keywords(recent):
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
        _update_last_topic(effective_user_id, sources)
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
            append_history(user_id, question)
            ctx = get_user_ctx(user_id)
            ctx["last_topic"] = topic
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
        history, profile = await _build_request_payload(user_id, question)
        ctx = get_user_ctx(user_id)
        last_topic = ctx.get("last_topic")
        if _should_contextualize_cake_fee(question, last_topic):
            context_question = (
                "Контекст: обсуждаем сладкий сбор за торт на празднике. "
                f"Вопрос: {question}"
            )
        elif last_topic and not _has_intent_hints(question):
            hint = _LAST_TOPIC_CONTEXT.get(last_topic)
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
