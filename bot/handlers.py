from __future__ import annotations

import logging
import time

import httpx
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from bot.keyboards import back_to_menu_kb, menu_kb
from bot.stickers import should_send_sticker, sticker_id_map


router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()

API_BASE = settings.api_base_url.rstrip("/")

FALLBACK_ERROR = (
    "Я сейчас не могу связаться с базой. Быстрее всего уточнить по телефону: +7 (831) 213-50-50"
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
}

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


async def _health_check() -> bool:
    timeout = httpx.Timeout(2.0, connect=2.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(f"{API_BASE}/health")
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            return False

    if resp.status_code != 200:
        return False
    try:
        data = resp.json()
    except Exception:
        return False
    return data.get("status") == "ok"


async def _ask_api(question: str) -> dict | None:
    timeout = httpx.Timeout(6.0, connect=6.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(f"{API_BASE}/ask", json={"question": question})
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            return None

    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except Exception:
        return None


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


async def _reply_with_answer(message: Message, question: str, *, keyboard) -> None:
    data = await _ask_api(question)
    if data is None:
        await message.answer(FALLBACK_ERROR, reply_markup=menu_kb())
        return

    answer = str(data.get("answer") or "").strip()
    sources = data.get("sources") or []

    if message.from_user:
        logger.info("user_id=%s question=%r sources=%s", message.from_user.id, question, sources)
    else:
        logger.info("user_id=unknown question=%r sources=%s", question, sources)

    if not answer:
        await message.answer(FALLBACK_ERROR, reply_markup=menu_kb())
        return

    await message.answer(answer, reply_markup=keyboard)


async def _handle_topic(message: Message, topic: str) -> None:
    question = TOPIC_QUESTIONS.get(topic)
    if not question:
        await message.answer("Не нашёл эту тему. Выберите из меню.", reply_markup=menu_kb())
        return
    await _reply_with_answer(message, question, keyboard=back_to_menu_kb())
    await _maybe_send_sticker(message, question)


@router.message(CommandStart())
async def start(message: Message) -> None:
    text = (
        "Привет! Я Джуси из Джунгли Сити (Нижний Новгород).\n"
        "Спроси меня про билеты, скидки, режим работы, праздники или правила — подскажу."
    )
    await message.answer(text, reply_markup=menu_kb())
    await message.answer("Парк выбран: НН.")

    ok = await _health_check()
    if ok:
        await message.answer("Я на связи!")
    else:
        await message.answer("Я отвечаю, но база сейчас недоступна, лучше уточнить по телефону.")


@router.message(Command("menu"))
async def menu(message: Message) -> None:
    await message.answer("Меню тем:", reply_markup=menu_kb())
    ok = await _health_check()
    if ok:
        await message.answer("Я на связи!")
    else:
        await message.answer("Я отвечаю, но база сейчас недоступна, лучше уточнить по телефону.")


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    text = (
        "Я подсказываю по парку: билеты, скидки, режим работы, правила, праздники и контакты.\n"
        "Можно написать вопрос или выбрать тему в меню ниже."
    )
    await message.answer(text, reply_markup=menu_kb())


@router.message(Command("prices"))
async def prices_cmd(message: Message) -> None:
    await _handle_topic(message, "prices")


@router.message(Command("discounts"))
async def discounts_cmd(message: Message) -> None:
    await _handle_topic(message, "discounts")


@router.message(Command("hours"))
async def hours_cmd(message: Message) -> None:
    await _handle_topic(message, "hours")


@router.callback_query(F.data == "menu")
async def menu_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer("Меню тем:", reply_markup=menu_kb())


@router.callback_query(F.data.startswith("topic:"))
async def topic_callback(callback: CallbackQuery) -> None:
    if not callback.data:
        return

    _, topic = callback.data.split(":", 1)
    await callback.answer()

    if callback.message:
        await _handle_topic(callback.message, topic)


@router.message()
async def any_text(message: Message) -> None:
    if not message.text:
        return

    question = message.text.strip()
    if not question:
        return

    await _reply_with_answer(message, question, keyboard=menu_kb())

    if message.from_user and _should_send_booking_hint(question, message.from_user.id):
        await message.answer("Если хотите, могу сразу дать контакт отдела праздников для брони: +7 962 509-74-93")

    await _maybe_send_sticker(message, question)
