from __future__ import annotations

import logging
from pathlib import Path

import httpx
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards import main_menu_kb
from bot.stickers import STICKER_FILE_ID_MAP, should_send_sticker, sticker_policy


router = Router()
logger = logging.getLogger(__name__)


def _load_contacts_text() -> str:
    p = Path("kb/nn/core/contacts.md")
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


def _fallback_contact_message() -> str:
    contacts = _load_contacts_text()
    if contacts:
        return (
            "Сейчас не получается быстро ответить в чате. Лучше уточнить у администратора/отдела праздников.\n\n"
            f"{contacts}"
        )
    return "Сейчас не получается быстро ответить в чате. Лучше уточнить у администратора/отдела праздников."


async def _ask_api(question: str) -> dict | None:
    url = "http://localhost:8000/ask"
    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json={"question": question})
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            return None

    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except Exception:
        return None


@router.message(CommandStart())
async def start(message: Message) -> None:
    text = (
        "Привет! Я Джуси из Джунгли Сити (Нижний Новгород).\n"
        "Спроси меня про билеты, скидки, режим работы, праздники или правила — подскажу."
    )
    await message.answer(text, reply_markup=main_menu_kb())
    await message.answer("Парк выбран: НН.")


@router.message()
async def any_text(message: Message) -> None:
    if not message.text:
        return

    question = message.text.strip()
    if not question:
        return

    if message.from_user:
        sticker_policy.record_user_message(message.from_user.id)

    data = await _ask_api(question)
    if data is None:
        await message.answer(_fallback_contact_message(), reply_markup=main_menu_kb())
        return

    answer = str(data.get("answer") or "").strip()
    sources = data.get("sources") or []

    if sources:
        logger.info("sources=%s", sources)

    if not answer:
        await message.answer(_fallback_contact_message(), reply_markup=main_menu_kb())
        return

    await message.answer(answer, reply_markup=main_menu_kb())

    # Optional: stickers are used rarely, and we don't have real sticker file_id values yet.
    if message.from_user and sticker_policy.can_send_now(message.from_user.id):
        decision = should_send_sticker(question)
        if decision.send:
            logger.info("sticker_decision=%s", decision.sticker_key)
            # TODO: send_sticker(STICKER_FILE_ID_MAP[decision.sticker_key])
            # Example:
            # await message.answer_sticker(STICKER_FILE_ID_MAP[decision.sticker_key])
            sticker_policy.mark_sent(message.from_user.id)
