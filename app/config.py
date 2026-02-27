import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    bot_token: str
    db_url: str
    initial_admin_ids: List[int]
    initial_admin_usernames: List[str]


def _parse_admin_ids(raw: str | None) -> List[int]:
    if not raw:
        return []
    ids: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


def _parse_admin_usernames(raw: str | None) -> List[str]:
    if not raw:
        return []
    names: List[str] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        # normalize: remove leading '@', make lowercase
        normalized = part.lstrip("@").lower()
        if normalized:
            names.append(normalized)
    return names


def get_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set in environment")

    db_url = os.getenv("DB_URL", "sqlite+aiosqlite:///./inventory.db")
    initial_admin_ids = _parse_admin_ids(os.getenv("INITIAL_ADMIN_IDS"))
    initial_admin_usernames = _parse_admin_usernames(
        os.getenv("INITIAL_ADMIN_USERNAMES")
    )

    return Settings(
        bot_token=bot_token,
        db_url=db_url,
        initial_admin_ids=initial_admin_ids,
        initial_admin_usernames=initial_admin_usernames,
    )


