from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    api_base_url: str


def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").strip()
    return Settings(telegram_token=token, api_base_url=api_base_url)
