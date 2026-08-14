"""Configuration loaded from environment variables (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set")
    return value


def _load_admin_ids() -> tuple[int, ...]:
    raw = os.getenv("ADMIN_IDS", "")
    return tuple(int(x) for x in raw.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    bot_token: str
    spreadsheet_id: str
    google_credentials_path: str
    google_credentials_json: str
    meetings_sheet: str
    registrations_sheet: str
    books_sheet: str
    admin_ids: tuple[int, ...]


settings = Settings(
    bot_token=_require("BOT_TOKEN"),
    spreadsheet_id=_require("SPREADSHEET_ID"),
    google_credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json"),
    # Either GOOGLE_CREDENTIALS_PATH (a file, for local/Docker Compose use) or
    # GOOGLE_CREDENTIALS_JSON (the key's raw JSON content, for hosts with no
    # file mounting like Railway) must resolve to a real service account key.
    google_credentials_json=os.getenv("GOOGLE_CREDENTIALS_JSON", ""),
    meetings_sheet=os.getenv("MEETINGS_SHEET", "Meetings"),
    registrations_sheet=os.getenv("REGISTRATIONS_SHEET", "Registrations"),
    books_sheet=os.getenv("BOOKS_SHEET", "Books"),
    admin_ids=_load_admin_ids(),
)
