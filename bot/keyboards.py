from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Цены", callback_data="topic:prices")],
            [InlineKeyboardButton(text="Скидки", callback_data="topic:discounts")],
            [InlineKeyboardButton(text="День рождения", callback_data="topic:birthday")],
            [InlineKeyboardButton(text="Правила", callback_data="topic:rules")],
            [InlineKeyboardButton(text="VR", callback_data="topic:vr")],
            [InlineKeyboardButton(text="Фиджитал", callback_data="topic:phygital")],
            [InlineKeyboardButton(text="Контакты", callback_data="topic:contacts")],
        ]
    )
