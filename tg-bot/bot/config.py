"""Config from env vars. Loaded once at startup."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Config:
    bot_token: str
    model_url: str
    request_timeout_s: float
    admin_user_ids: frozenset[int]

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit(
                "BOT_TOKEN is empty. Copy .env.example to .env and set it."
            )
        raw_admins = os.getenv("ADMIN_USER_IDS", "")
        admins = frozenset(
            int(x.strip()) for x in raw_admins.split(",") if x.strip().isdigit()
        )
        return cls(
            bot_token=token,
            model_url=os.getenv("MODEL_URL", "http://localhost:8000").rstrip("/"),
            request_timeout_s=float(os.getenv("MODEL_TIMEOUT_S", "20")),
            admin_user_ids=admins,
        )


CONFIG = Config.from_env() if os.getenv("BOT_TOKEN") else None
