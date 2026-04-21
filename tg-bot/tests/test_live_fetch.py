"""
Live fetcher test — no bot, no model, just the pipeline up to model input.

Takes a Telegram message URL, runs it through the same fetch path the bot
would use, and prints every step so you can see exactly what text gets
extracted and what payload will eventually be sent to the model.

Usage:
    python tests/test_live_fetch.py https://t.me/rian_ru/12345
    python tests/test_live_fetch.py                 # will prompt for URL

You can also feed a text to the model step directly (skip the fetch) with:
    python tests/test_live_fetch.py --text "На Украине биолаборатории..."
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.schemas import DetectRequest
from bot.tg_fetch import FetchFailure, fetch_message, parse_tg_url


def hr(title: str = "", char: str = "─") -> None:
    if title:
        print()
        print(f"{char * 2} {title} {char * (66 - len(title))}")
    else:
        print(char * 70)


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def fail(msg: str) -> None:
    print(f"  ✗ {msg}")


def info(label: str, value: str) -> None:
    print(f"  {label:<14} {value}")


async def run_url_pipeline(url: str) -> None:
    hr("INPUT")
    info("url:", url)

    # ── Step 1: parse ──────────────────────────────────────────
    hr("STEP 1  URL parsing")
    parsed = parse_tg_url(url)
    if isinstance(parsed, FetchFailure):
        fail(f"parse failed: {parsed.error.value}")
        print(f"     {parsed.hint}")
        sys.exit(2)
    channel, msg_id = parsed
    ok(f"valid public TG url")
    info("channel:", channel)
    info("message_id:", msg_id)
    info("preview url:", f"https://t.me/s/{channel}/{msg_id}")

    # ── Step 2: fetch + extract ────────────────────────────────
    hr("STEP 2  HTTP fetch + HTML extraction")
    t0 = time.monotonic()
    result = await fetch_message(url)
    elapsed_ms = (time.monotonic() - t0) * 1000

    if isinstance(result, FetchFailure):
        fail(f"{result.error.value} ({elapsed_ms:.0f} ms)")
        print(f"     {result.hint}")
        sys.exit(3)

    ok(f"fetched + parsed in {elapsed_ms:.0f} ms")
    info("channel:", result.channel)
    info("message_id:", result.message_id)
    info("source_url:", result.source_url)
    info("text length:", f"{len(result.text)} chars, "
                         f"{len(result.text.splitlines())} lines")

    hr("EXTRACTED TEXT", "┄")
    for line in (result.text.splitlines() or [""]):
        print(f"  │ {line}")
    hr()

    # ── Step 3: show model payload ─────────────────────────────
    hr("STEP 3  Payload that would be POSTed to /detect")
    req = DetectRequest(
        text=result.text,
        channel=result.channel,
        message_id=result.message_id,
        source_url=result.source_url,
    )
    payload = req.model_dump()
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    hr()
    print()
    print("  ✓ Pipeline OK. When the real model is up, it will receive")
    print("    exactly this JSON and return a DetectResponse.")
    print()


async def run_text_only(text: str) -> None:
    """Skip fetch, go straight to 'what would be sent to the model'."""
    hr("INPUT (text mode, no fetch)")
    info("length:", f"{len(text)} chars")

    hr("TEXT", "┄")
    for line in text.splitlines() or [""]:
        print(f"  │ {line}")
    hr()

    hr("Payload for /detect")
    req = DetectRequest(text=text)
    print(json.dumps(req.model_dump(), indent=2, ensure_ascii=False))
    hr()
    print()
    print("  ✓ This is what the model will receive when a user pastes text")
    print("    instead of a URL.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip())
    ap.add_argument("url_or_text", nargs="?", help="Telegram message URL (or use --text)")
    ap.add_argument("--text", help="Skip fetch, test the text-only path to the model")
    args = ap.parse_args()

    if args.text:
        asyncio.run(run_text_only(args.text))
        return

    url = args.url_or_text or input("Telegram message URL: ").strip()
    if not url:
        print("No URL given.")
        sys.exit(1)
    asyncio.run(run_url_pipeline(url))


if __name__ == "__main__":
    main()
