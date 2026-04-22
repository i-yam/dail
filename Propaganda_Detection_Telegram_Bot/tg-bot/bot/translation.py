"""
Language detection + translation to English.

Used by handlers to normalize input before calling the model:
    RU/UK/DE/... text  ──►  detect language  ──►  translate to EN  ──►  model

Translation chain (falls back on failure):
    1. Google Translate (via deep-translator; no API key)
    2. MyMemory        (via deep-translator; no API key, EU-backed)

If all providers fail, we fall back to sending the original text —
the real model will use multilingual embeddings anyway, and the bot
shouldn't hard-fail on a network hiccup.

Turn off entirely by setting env AUTO_TRANSLATE=0.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from enum import Enum

from deep_translator import GoogleTranslator, MyMemoryTranslator
from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException

# deterministic detection across runs
DetectorFactory.seed = 42

log = logging.getLogger(__name__)

ENABLED = os.getenv("AUTO_TRANSLATE", "1") != "0"
# Texts in these languages are passed through without translation
PASSTHROUGH_LANGS = {"en"}
# Some ISO codes differ between langdetect and Google Translate
_LANG_CODE_MAP = {
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
    "he": "iw",  # langdetect returns "he", google wants "iw"
}


class TranslationStatus(str, Enum):
    PASSTHROUGH = "passthrough"         # already English, not translated
    TRANSLATED = "translated"           # successfully translated
    SKIPPED = "skipped"                 # AUTO_TRANSLATE=0
    UNDETECTED = "undetected"           # language detection failed, passed through
    FAILED = "failed"                   # all translators failed, passed through


@dataclass
class LangResult:
    status: TranslationStatus
    detected_lang: str | None          # e.g. "ru", "uk"
    confidence: float                  # 0..1
    english_text: str                  # what to send to the model
    original_text: str                 # always the input
    provider: str | None = None        # "google" | "mymemory" | None
    error: str | None = None           # when FAILED


def _detect(text: str) -> tuple[str, float] | None:
    """Return (lang_code, confidence) or None if detection failed."""
    try:
        langs = detect_langs(text)
    except LangDetectException:
        return None
    if not langs:
        return None
    top = langs[0]
    return top.lang, top.prob


def _normalize_code(code: str) -> str:
    return _LANG_CODE_MAP.get(code.lower(), code.lower())


def _translate_sync(text: str, source: str) -> tuple[str, str]:
    """Try providers in order. Returns (translated_text, provider_name)."""
    src = _normalize_code(source)

    # 1) Google (fastest, highest quality)
    try:
        out = GoogleTranslator(source=src, target="en").translate(text)
        if out and out.strip():
            return out, "google"
    except Exception as e:  # deep_translator raises various subclasses
        log.info("google translate failed: %s; falling back to mymemory", e.__class__.__name__)

    # 2) MyMemory fallback
    try:
        # mymemory takes language *names* via a different code scheme
        out = MyMemoryTranslator(source=src, target="en").translate(text)
        if out and out.strip():
            return out, "mymemory"
    except Exception as e:
        log.info("mymemory translate also failed: %s", e.__class__.__name__)

    raise RuntimeError("all translators failed")


async def detect_and_translate(text: str) -> LangResult:
    """
    Main entry point. Runs blocking libs in a thread so aiogram stays async.
    Never raises — always returns a LangResult with sensible fallback.
    """
    original = text

    if not ENABLED:
        return LangResult(
            status=TranslationStatus.SKIPPED,
            detected_lang=None,
            confidence=0.0,
            english_text=original,
            original_text=original,
        )

    # detection
    det = await asyncio.to_thread(_detect, text)
    if det is None:
        return LangResult(
            status=TranslationStatus.UNDETECTED,
            detected_lang=None,
            confidence=0.0,
            english_text=original,
            original_text=original,
        )
    lang, confidence = det

    if lang in PASSTHROUGH_LANGS:
        return LangResult(
            status=TranslationStatus.PASSTHROUGH,
            detected_lang=lang,
            confidence=confidence,
            english_text=original,
            original_text=original,
        )

    # translation
    try:
        translated, provider = await asyncio.to_thread(_translate_sync, text, lang)
    except Exception as e:
        log.warning("translation pipeline failed, using original: %s", e)
        return LangResult(
            status=TranslationStatus.FAILED,
            detected_lang=lang,
            confidence=confidence,
            english_text=original,
            original_text=original,
            error=str(e),
        )

    return LangResult(
        status=TranslationStatus.TRANSLATED,
        detected_lang=lang,
        confidence=confidence,
        english_text=translated,
        original_text=original,
        provider=provider,
    )
