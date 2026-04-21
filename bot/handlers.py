from __future__ import annotations
"""
bot/handlers.py
All command and message handlers for the Propaganda Watchdog Bot.

Commands:
  /start          — welcome message
  /help           — list all commands
  /watch          — toggle real-time monitoring for this chat
  /analyze [N|text] — analyse last N stored messages, or a specific text
  /report [N]     — show the last N flagged messages with receipts
  /cluster        — show narrative clusters over time
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.classifier import classify
from services.disinfo_pipeline import analyze_message_pipeline
from storage import db
from bot.formatter import (
    format_flag_alert,
    format_analyze_result,
    format_pipeline_decision,
    format_similar_articles,
    format_report,
    format_clusters,
    format_watch_on,
    format_watch_off,
)

logger = logging.getLogger(__name__)


# ── /start ────────────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "👁‍🗨 <b>Propaganda Watchdog</b>  —  DIAL 2026\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "I detect propaganda narratives in Telegram channels.\n\n"
        "🔧 <b>Quick start:</b>\n"
        "  1. Add me to your group/channel as admin\n"
        "  2. Run /watch to start real-time monitoring\n"
        "  3. Use /report to see flagged messages\n\n"
        "Type /help for all commands."
    )


# ── /help ─────────────────────────────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "🤖 <b>Commands</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "/watch       — Toggle real-time monitoring on/off\n"
        "/analyze     — Analyse last 10 stored messages\n"
        "/analyze 20  — Analyse last 20 stored messages\n"
        "/analyze &lt;text&gt; — Analyse a specific text snippet\n"
        "/report      — Show last 10 flagged messages (receipts)\n"
        "/report 20   — Show last 20 flagged messages\n"
        "/cluster     — Map narrative clusters over time\n"
        "/help        — Show this message\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Watch mode must be enabled to collect messages automatically.\n"
        "Without it, use /analyze &lt;your text&gt; for one-off checks."
    )


# ── /watch ────────────────────────────────────────────────────────────────────

async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    if db.is_watch_enabled(chat_id):
        db.disable_watch(chat_id)
        await update.message.reply_html(format_watch_off())
        logger.info("Watch disabled for chat %s", chat_id)
    else:
        db.enable_watch(chat_id)
        await update.message.reply_html(format_watch_on())
        logger.info("Watch enabled for chat %s", chat_id)


# ── /analyze ──────────────────────────────────────────────────────────────────

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    args = context.args  # list of words after /analyze

    # Case 1: /analyze <text to check> — one-off text analysis
    if args and not args[0].isdigit():
        text = " ".join(args)
        await update.message.reply_html("🔍 Analysing…")
        pipeline = await analyze_message_pipeline(text, top_k=3, verify_with_llm=True)

        # Save to DB regardless of result
        msg_id = db.save_message(
            chat_id=chat_id,
            user_id=update.effective_user.id if update.effective_user else None,
            username=update.effective_user.username if update.effective_user else None,
            text=text,
        )

        if pipeline.matches:
            top_match = pipeline.matches[0]
            db.save_flagged(
                msg_id,
                chat_id,
                top_match.article.title,
                top_match.score,
                None,
            )
            await update.message.reply_html(
                format_pipeline_decision(
                    matches=pipeline.matches,
                    classifier_prediction=None,
                    fragment_review=None,
                )
            )
            return

        result = pipeline.classifier_prediction
        if result is None:
            await update.message.reply_html(
                "⚠️ Could not run classifier fallback and no verified DB match was found."
            )
            return

        if result.is_propaganda:
            db.save_flagged(msg_id, chat_id, result.narrative_label, result.confidence, result.cluster_id)

        await update.message.reply_html(
            format_pipeline_decision(
                matches=[],
                classifier_prediction=result,
                fragment_review=pipeline.fragment_review,
            )
        )
        return

    # Case 2: /analyze [N] — analyse last N stored messages
    limit = int(args[0]) if args and args[0].isdigit() else 10
    limit = min(limit, 50)  # cap at 50

    messages = db.get_recent_messages(chat_id, limit)
    if not messages:
        await update.message.reply_html(
            "📭 <b>No stored messages found.</b>\n"
            "Enable /watch first so I can collect messages, "
            "or use /analyze &lt;text&gt; to analyse a specific message."
        )
        return

    await update.message.reply_html(f"🔍 Analysing {len(messages)} stored message(s)…")

    propaganda_count = 0
    for msg in messages:
        result = await classify(msg["text"])
        if result.is_propaganda:
            propaganda_count += 1
            db.save_flagged(msg["id"], chat_id, result.narrative_label, result.confidence, result.cluster_id)
            await update.message.reply_html(
                format_flag_alert(
                    text=msg["text"],
                    username=msg["username"],
                    confidence=result.confidence,
                    label=result.narrative_label,
                    cluster_id=result.cluster_id,
                )
            )

    summary = (
        f"✅ <b>Analysis complete.</b>\n"
        f"Checked {len(messages)} message(s).  "
        f"Found <b>{propaganda_count}</b> propaganda hit(s).\n"
        f"Use /report to see all receipts."
    )
    await update.message.reply_html(summary)
# ── /report ───────────────────────────────────────────────────────────────────

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    limit = 10
    if context.args and context.args[0].isdigit():
        limit = min(int(context.args[0]), 50)

    rows = db.get_flagged_for_chat(chat_id, limit)
    await update.message.reply_html(format_report(list(rows)))


# ── /cluster ──────────────────────────────────────────────────────────────────

async def cluster_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    clusters = db.get_clusters_for_chat(chat_id)
    await update.message.reply_html(format_clusters(clusters))


# ── Real-time message watcher ─────────────────────────────────────────────────

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Fires on every non-command message in a watched chat.
    Stores the message and flags it if the classifier returns propaganda.
    """
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id

    # Only process if watch mode is active for this chat
    if not db.is_watch_enabled(chat_id):
        return

    text = update.message.text
    user = update.effective_user
    username = user.username if user else None
    user_id = user.id if user else None

    # Persist the message
    msg_id = db.save_message(chat_id, user_id, username, text)

    # Classify asynchronously
    result = await classify(text)
    logger.debug("chat=%s  propaganda=%s  conf=%.2f  label=%s", chat_id, result.is_propaganda, result.confidence, result.narrative_label)

    if result.is_propaganda:
        db.save_flagged(msg_id, chat_id, result.narrative_label, result.confidence, result.cluster_id)
        await update.message.reply_html(
            format_flag_alert(
                text=text,
                username=username,
                confidence=result.confidence,
                label=result.narrative_label,
                cluster_id=result.cluster_id,
            )
        )
