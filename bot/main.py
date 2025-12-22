from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import get_settings
from bot.handlers import router


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO)


def _build_bot() -> Bot:
    settings = get_settings()
    return Bot(token=settings.telegram_token)


async def main() -> None:
    _setup_logging()

    bot = _build_bot()
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
