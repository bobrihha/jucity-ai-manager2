from __future__ import annotations

import logging

import httpx
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from bot.keyboards import menu_kb
from bot.stickers import should_send_sticker, sticker_id_map


router = Router()
logger = logging.getLogger(__name__)
settings = get_settings()

API_BASE = settings.api_base_url.rstrip("/")

FALLBACK_ERROR = "Я сейчас не могу связаться с базой. Позвоните, пожалуйста, в парк: +7 (831) 213-50-50"

TOPIC_QUESTIONS = {
    "prices": "Сколько стоит билет в субботу и в будний день?",
    "discounts": "Какие скидки есть (ОВЗ, многодетные, после 20:00, именинники)?",
    "birthday": "Как отпраздновать день рождения: условия, комнаты, время, что включено?",
    "rules": "Какие правила посещения (носки, еда, сопровождение)?",
    "vr": "VR входит в билет? Какие условия и где посмотреть цены?",
    "phygital": "Фиджитал входит в билет? Сколько стоит и как работает?",
    "contacts": "Подскажи контакты и адрес, как добраться",
}


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
    timeout = httpx.Timeout(15.0, connect=5.0)
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


@router.callback_query(F.data.startswith("topic:"))
async def topic_callback(callback: CallbackQuery) -> None:
    if not callback.data:
        return

    _, topic = callback.data.split(":", 1)
    question = TOPIC_QUESTIONS.get(topic)
    if not question:
        await callback.answer()
        return

    data = await _ask_api(question)
    await callback.answer()

    if data is None:
        if callback.message:
            await callback.message.answer(FALLBACK_ERROR, reply_markup=menu_kb())
        return

    answer = str(data.get("answer") or "").strip()
    sources = data.get("sources") or []
    if sources:
        logger.info("sources=%s", sources)

    if not answer:
        if callback.message:
            await callback.message.answer(FALLBACK_ERROR, reply_markup=menu_kb())
        return

    if callback.message:
        await callback.message.answer(answer, reply_markup=menu_kb())
        await _maybe_send_sticker(callback.message, question)


@router.message()
async def any_text(message: Message) -> None:
    if not message.text:
        return

    question = message.text.strip()
    if not question:
        return

    data = await _ask_api(question)
    if data is None:
        await message.answer(FALLBACK_ERROR, reply_markup=menu_kb())
        return

    answer = str(data.get("answer") or "").strip()
    sources = data.get("sources") or []
    if sources:
        logger.info("sources=%s", sources)

    if not answer:
        await message.answer(FALLBACK_ERROR, reply_markup=menu_kb())
        return

    await message.answer(answer, reply_markup=menu_kb())
    await _maybe_send_sticker(message, question)
