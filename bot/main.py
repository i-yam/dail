"""
bot/main.py
Entry point for the Propaganda Watchdog Bot.

Run with:
    python bot/main.py

Requires:
    TELEGRAM_BOT_TOKEN  in .env (or environment)
    CLASSIFIER_API_URL  in .env (optional — falls back to mock classifier)
"""

import logging
import os
import sys
from pathlib import Path

# ── Make project root importable from any cwd ─────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from storage.db import init_db
from bot.handlers import (
    start_command,
    help_command,
    watch_command,
    analyze_command,
    report_command,
    cluster_command,
    message_handler,
)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.critical("TELEGRAM_BOT_TOKEN is not set. Add it to your .env file.")
        sys.exit(1)

    # Initialise database
    init_db()
    logger.info("Database ready.")

    # Build the application
    app = ApplicationBuilder().token(token).build()

    # ── Register command handlers ─────────────────────────────────────────────
    app.add_handler(CommandHandler("start",   start_command))
    app.add_handler(CommandHandler("help",    help_command))
    app.add_handler(CommandHandler("watch",   watch_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("report",  report_command))
    app.add_handler(CommandHandler("cluster", cluster_command))

    # ── Real-time message watcher (non-command text only) ─────────────────────
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
    )

    # ── Start polling ─────────────────────────────────────────────────────────
    classifier_url = os.getenv("CLASSIFIER_API_URL", "NOT SET (using mock)")
    logger.info("▶  Propaganda Watchdog Bot is running.")
    logger.info("   Classifier API : %s", classifier_url)
    logger.info("   Press Ctrl+C to stop.\n")

    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
