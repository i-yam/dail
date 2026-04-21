"""
Shared wire schemas for the bot <-> model HTTP contract.

This is the SINGLE source of truth. Both the bot (client) and the FastAPI
service (server) import from here. If you change fields, both sides update
automatically.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    MATCH = "match"
    WEAK_MATCH = "weak_match"
    NO_MATCH = "no_match"
    ERROR = "error"
    NO_INPUT = "no_input"


class DetectRequest(BaseModel):
    # Text the model should analyze. If the input was not English and
    # auto-translate succeeded, this is the English translation.
    text: str = Field(..., description="Text to analyze (usually English)")

    # Original (possibly non-English) text. Present when translation happened.
    # A multilingual model may prefer this to the translation.
    original_text: str | None = Field(None, description="Untranslated original, if any")

    # ISO 639-1 language code of the original message, e.g. "ru", "uk", "en".
    language: str | None = Field(None, description="Detected source language")

    channel: str | None = Field(None, description="TG channel username, without @")
    message_id: str | None = Field(None, description="TG message id")
    source_url: str | None = Field(None, description="Original message URL if any")


class Receipt(BaseModel):
    date: str               # ISO date, e.g. "2022-03-23"
    outlet: str             # e.g. "RT Arabic"
    title: str
    url: str                # link to EUvsDisinfo case
    similarity: float       # 0..1


class DetectResponse(BaseModel):
    verdict: Verdict
    confidence: float = 0.0          # 0..1
    narrative_id: str | None = None
    narrative_label: str | None = None
    explanation: str = ""
    receipts: list[Receipt] = []
    legal_notes: str | None = None   # "FIMI: ... / DSA: ..."
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    error: str | None = None         # machine-readable error code when verdict=error/no_input
