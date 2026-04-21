"""Entry point: `python -m bot.main`. Long-polls Telegram."""
from __future__ import annotations

import asyncio
import logging
import sys

# Force UTF-8 stdout — Windows PowerShell 5.1 defaults to cp1252 which mangles
# Cyrillic. No-op on Linux/Mac or newer Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import Config
from .handlers import router
from .model_client import ModelClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("bot")


async def main() -> None:
    cfg = Config.from_env()
    log.info("model url: %s", cfg.model_url)

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    model = ModelClient(cfg.model_url, cfg.request_timeout_s)

    # Warn early if the model is unreachable — bot still starts, it'll just
    # return error verdicts until the model comes up.
    if await model.health():
        log.info("model service reachable")
    else:
        log.warning("model service NOT reachable at %s — bot will return errors", cfg.model_url)

    dp = Dispatcher()
    # inject model client into handler kwargs via aiogram's workflow_data
    dp["model"] = model
    dp.include_router(router)

    me = await bot.get_me()
    log.info("bot online as @%s (id=%s)", me.username, me.id)

    try:
        await dp.start_polling(bot, handle_signals=True)
    finally:
        await model.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
