"""Settings loaded from environment variables (and an optional .env file)."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int | None) -> int | None:
    value = os.getenv(name, "").strip()
    return int(value) if value else default


def _delay(raw: str) -> tuple[float, float]:
    lo, _, hi = raw.partition(",")
    lo_f = float(lo)
    hi_f = float(hi) if hi else lo_f
    return (min(lo_f, hi_f), max(lo_f, hi_f))


@dataclass
class Config:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("MODEL", "claude-opus-5-5"))
    persona: str = field(default_factory=lambda: os.getenv("PERSONA", "gerald"))
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "timewaste.db"))
    reply_delay: tuple[float, float] = field(
        default_factory=lambda: _delay(os.getenv("REPLY_DELAY", "20,120"))
    )

    # Userbot (Telethon)
    api_id: int | None = field(default_factory=lambda: _int("TG_API_ID", None))
    api_hash: str = field(default_factory=lambda: os.getenv("TG_API_HASH", ""))
    phone: str = field(default_factory=lambda: os.getenv("TG_PHONE", ""))
    session_name: str = field(default_factory=lambda: os.getenv("TG_SESSION", "timewaste"))
    auto_engage: bool = field(default_factory=lambda: _bool("AUTO_ENGAGE", False))
    scam_threshold: int = field(default_factory=lambda: _int("SCAM_THRESHOLD", 3) or 3)

    # Bot API (python-telegram-bot)
    bot_token: str = field(default_factory=lambda: os.getenv("TG_BOT_TOKEN", ""))
    owner_id: int | None = field(default_factory=lambda: _int("OWNER_ID", None))
