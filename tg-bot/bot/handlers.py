"""Command handlers. Routing logic only — parsing lives in tg_fetch, rendering in formatters."""
from __future__ import annotations

import logging
import time
import uuid

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from .formatters import ABOUT, HELP, WELCOME, format_analysis, format_details
from .model_client import ModelClient
from .schemas import DetectRequest, DetectResponse, Verdict
from .tg_fetch import (
    FetchFailure,
    FetchedMessage,
    fetch_message,
    looks_like_tg_url,
)
from .trace import Trace
from .translation import LangResult, TranslationStatus, detect_and_translate

log = logging.getLogger(__name__)
router = Router()

_response_cache: dict[str, DetectResponse] = {}
CACHE_LIMIT = 500


def _cache_response(resp: DetectResponse) -> str:
    key = uuid.uuid4().hex[:10]
    if len(_response_cache) > CACHE_LIMIT:
        for k in list(_response_cache.keys())[: CACHE_LIMIT // 5]:
            _response_cache.pop(k, None)
    _response_cache[key] = resp
    return key


def _result_keyboard(cache_key: str, resp: DetectResponse) -> InlineKeyboardMarkup | None:
    if resp.verdict in (Verdict.ERROR, Verdict.NO_INPUT, Verdict.NO_MATCH):
        return None
    buttons = [[InlineKeyboardButton(text="📖 Show details", callback_data=f"d:{cache_key}")]]
    if resp.receipts:
        buttons[0].append(
            InlineKeyboardButton(text="🌐 Open EUvsDisinfo", url=resp.receipts[0].url)
        )
    buttons.append(
        [InlineKeyboardButton(text="⚠️ False positive", callback_data=f"fp:{cache_key}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _start_trace(message: Message, raw: str) -> Trace:
    return Trace.start(
        user_id=message.from_user.id if message.from_user else 0,
        username=message.from_user.username if message.from_user else None,
        chat_type=message.chat.type,
        raw=raw,
    )


# ---- command handlers ------------------------------------------------------


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(WELCOME, disable_web_page_preview=True)


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(HELP, disable_web_page_preview=True)


@router.message(Command("about"))
async def on_about(message: Message) -> None:
    await message.answer(ABOUT, disable_web_page_preview=True)


@router.message(Command("check"))
async def on_check(message: Message, model: ModelClient) -> None:
    payload = ((message.text or "").split(maxsplit=1) + [""])[1].strip()
    if not payload:
        await message.answer(
            "Usage: <code>/check &lt;t.me link or text&gt;</code>\n"
            "Or just send me a link / text without /check."
        )
        return
    tr = _start_trace(message, payload)
    await _handle_input(message, model, payload, tr)


@router.message(F.text & ~F.text.startswith("/"))
async def on_plain_text(message: Message, model: ModelClient) -> None:
    payload = (message.text or "").strip()
    if not payload:
        return
    tr = _start_trace(message, payload)
    await _handle_input(message, model, payload, tr)


# ---- core flow -------------------------------------------------------------


async def _run_translation(original_text: str, tr: Trace) -> LangResult:
    """Normalize to English, logging every step to the trace."""
    tr.step("STEP 2 — Language detection + translation")
    t0 = time.monotonic()
    lang_res = await detect_and_translate(original_text)
    elapsed_ms = (time.monotonic() - t0) * 1000

    if lang_res.status == TranslationStatus.PASSTHROUGH:
        tr.ok(f"already English ({elapsed_ms:.0f}ms), no translation needed")
        tr.kv("confidence:", f"{lang_res.confidence:.2f}")
    elif lang_res.status == TranslationStatus.TRANSLATED:
        tr.ok(f"translated {lang_res.detected_lang}→en in {elapsed_ms:.0f}ms via {lang_res.provider}")
        tr.kv("detected:", f"{lang_res.detected_lang} (conf {lang_res.confidence:.2f})")
        tr.text_block("translated text:", lang_res.english_text)
    elif lang_res.status == TranslationStatus.UNDETECTED:
        tr.fail(f"language detection failed ({elapsed_ms:.0f}ms), passing original through")
    elif lang_res.status == TranslationStatus.FAILED:
        tr.fail(f"translation failed via all providers ({elapsed_ms:.0f}ms), passing original through")
        tr.kv("detected:", lang_res.detected_lang or "?")
        tr.kv("error:", lang_res.error or "?")
    else:  # SKIPPED
        tr.kv("status:", "skipped (AUTO_TRANSLATE=0)")

    return lang_res


def _build_request(
    lang_res: LangResult,
    *,
    channel: str | None = None,
    message_id: str | None = None,
    source_url: str | None = None,
) -> DetectRequest:
    return DetectRequest(
        text=lang_res.english_text,
        original_text=(
            lang_res.original_text
            if lang_res.status == TranslationStatus.TRANSLATED
            else None
        ),
        language=lang_res.detected_lang,
        channel=channel,
        message_id=message_id,
        source_url=source_url,
    )


async def _handle_input(
    message: Message, model: ModelClient, payload: str, tr: Trace
) -> None:
    is_url = looks_like_tg_url(payload.split()[0]) if payload else False

    if is_url:
        # ── URL mode ─────────────────────────────────────────────
        url = payload.split()[0]
        tr.step("STEP 1 — URL mode")
        tr.kv("url:", url)

        status = await message.answer("⏳ Fetching the message…")

        t0 = time.monotonic()
        fetched = await fetch_message(url)
        fetch_ms = (time.monotonic() - t0) * 1000

        if isinstance(fetched, FetchFailure):
            tr.fail(f"fetch failed: {fetched.error.value} ({fetch_ms:.0f}ms)")
            tr.kv("hint:", fetched.hint)
            await status.edit_text(f"❌ {fetched.hint}")
            tr.finish(f"error:{fetched.error.value}")
            return

        tr.ok(f"fetched & parsed in {fetch_ms:.0f}ms")
        tr.kv("channel:", fetched.channel)
        tr.kv("message_id:", fetched.message_id)
        tr.kv("text length:", f"{len(fetched.text)} chars")
        tr.text_block("extracted text:", fetched.text)

        await status.edit_text("⏳ Detecting language…")
        lang_res = await _run_translation(fetched.text, tr)

        req = _build_request(
            lang_res,
            channel=fetched.channel,
            message_id=fetched.message_id,
            source_url=fetched.source_url,
        )
        await _run_detection(model, req, tr, status)
        source_hint = f"@{fetched.channel}/{fetched.message_id}"
        # result already sent by _run_detection
        return

    # ── Text mode ─────────────────────────────────────────────
    tr.step("STEP 1 — Text mode (no fetch)")
    tr.kv("text length:", f"{len(payload)} chars")

    if len(payload) < 20:
        tr.fail("text too short (min 20 chars)")
        await message.answer(
            "The text is too short to analyze meaningfully (min 20 characters). "
            "Paste the full post or a link to it."
        )
        tr.finish("error:too_short")
        return

    tr.text_block("text:", payload)
    status = await message.answer("⏳ Detecting language…")

    lang_res = await _run_translation(payload, tr)
    req = _build_request(lang_res)
    await _run_detection(model, req, tr, status)


async def _run_detection(
    model: ModelClient, req: DetectRequest, tr: Trace, status: Message
) -> None:
    tr.step("STEP 3 — Calling model /detect")
    tr.json_block("payload:", req.model_dump())

    await status.edit_text("⏳ Analyzing…")
    t0 = time.monotonic()
    resp = await model.detect(req)
    model_ms = (time.monotonic() - t0) * 1000
    tr.ok(f"model replied in {model_ms:.0f}ms")
    tr.kv("verdict:", resp.verdict.value)
    tr.kv("confidence:", f"{resp.confidence:.2f}")
    tr.kv("narrative:", resp.narrative_id or "-")
    tr.kv("receipts:", len(resp.receipts))

    source_hint = (
        f"@{req.channel}/{req.message_id}"
        if req.channel and req.message_id
        else None
    )
    await _send_result(status, resp, source_hint, edit=True)
    tr.finish(resp.verdict.value)


async def _send_result(
    status: Message,
    resp: DetectResponse,
    source_hint: str | None,
    *,
    edit: bool,
) -> None:
    key = _cache_response(resp)
    text = format_analysis(resp, source_hint=source_hint)
    kb = _result_keyboard(key, resp)
    if edit:
        await status.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    else:
        await status.answer(text, reply_markup=kb, disable_web_page_preview=True)


# ---- callback handlers -----------------------------------------------------


@router.callback_query(F.data.startswith("d:"))
async def on_details(cb: CallbackQuery) -> None:
    key = cb.data.removeprefix("d:")
    resp = _response_cache.get(key)
    if not resp:
        await cb.answer("This analysis expired. Send the link again.", show_alert=True)
        return
    await cb.answer()
    await cb.message.answer(format_details(resp), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("fp:"))
async def on_false_positive(cb: CallbackQuery) -> None:
    key = cb.data.removeprefix("fp:")
    resp = _response_cache.get(key)
    log.info(
        "false_positive_feedback user=%s narrative=%s confidence=%s",
        cb.from_user.id,
        resp.narrative_id if resp else "?",
        resp.confidence if resp else "?",
    )
    await cb.answer(
        "Thanks — feedback logged. It helps calibrate the model.",
        show_alert=False,
    )
