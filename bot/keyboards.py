from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Контакты"), KeyboardButton(text="Цены")],
            [KeyboardButton(text="Скидки"), KeyboardButton(text="Правила")],
        ],
        resize_keyboard=True,
        selective=True,
    )

