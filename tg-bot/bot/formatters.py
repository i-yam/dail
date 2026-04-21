"""Render model responses as Telegram HTML. All user-facing copy lives here."""
from __future__ import annotations

from html import escape

from .schemas import DetectResponse, Verdict

VERDICT_BADGE = {
    Verdict.MATCH: "🚩 <b>Match</b>",
    Verdict.WEAK_MATCH: "⚠️ <b>Weak match</b>",
    Verdict.NO_MATCH: "✅ <b>No match</b>",
    Verdict.ERROR: "❌ <b>Error</b>",
    Verdict.NO_INPUT: "❌ <b>No input</b>",
}

DISCLAIMER = (
    "\n\n<i>Not a verdict. This is a pattern-matching signal against the "
    "EUvsDisinfo database. Final judgment is yours.</i>"
)


def _fmt_confidence(c: float) -> str:
    return f"{c * 100:.0f}%"


def _shorten(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def format_analysis(resp: DetectResponse, source_hint: str | None = None) -> str:
    """Short inline reply. Detailed explanation goes behind a 'Show details' button."""
    badge = VERDICT_BADGE[resp.verdict]

    if resp.verdict == Verdict.ERROR:
        err = resp.error or "unknown"
        return (
            f"{badge}\n"
            f"The model service failed (<code>{escape(err)}</code>). "
            f"Try again in a moment."
        )

    if resp.verdict == Verdict.NO_INPUT:
        return (
            f"{badge}\n"
            f"The message didn't contain any usable text."
        )

    header = f"{badge} — confidence {_fmt_confidence(resp.confidence)}"

    if resp.verdict == Verdict.NO_MATCH:
        body = "No recurring propaganda narrative matched this message."
        return f"{header}\n{body}{DISCLAIMER}"

    # match / weak_match
    lines: list[str] = [header]
    if resp.narrative_label:
        lines.append(f"\n<b>Narrative:</b> {escape(resp.narrative_label)}")
    if resp.explanation:
        max_len = 900 if resp.verdict == Verdict.WEAK_MATCH else 300
        lines.append(f"\n{escape(_shorten(resp.explanation, max_len))}")

    if resp.receipts:
        lines.append("\n<b>Historical references:</b>")
        for r in resp.receipts[:3]:
            outlet = escape(r.outlet or "unknown outlet")
            title = escape(_shorten(r.title, 80))
            lines.append(f'• {r.date} — <a href="{escape(r.url)}">{title}</a> ({outlet})')

    if source_hint:
        lines.append(f"\n<i>Source: {escape(source_hint)}</i>")

    lines.append(DISCLAIMER)
    return "\n".join(lines)


def format_details(resp: DetectResponse) -> str:
    """Full explanation behind the 'Show details' button."""
    if resp.verdict in (Verdict.ERROR, Verdict.NO_INPUT, Verdict.NO_MATCH):
        return format_analysis(resp)

    parts: list[str] = []
    parts.append(f"{VERDICT_BADGE[resp.verdict]} — confidence {_fmt_confidence(resp.confidence)}")
    if resp.narrative_label:
        parts.append(f"\n<b>Narrative:</b> {escape(resp.narrative_label)}")
    if resp.narrative_id and not resp.narrative_id.startswith("classifier_"):
        parts.append(f"<b>ID:</b> <code>{escape(resp.narrative_id)}</code>")
    if resp.explanation:
        parts.append(f"\n<b>Why flagged:</b>\n{escape(resp.explanation)}")
    if resp.legal_notes:
        parts.append(f"\n<b>Legal framing:</b>\n{escape(resp.legal_notes)}")

    if resp.receipts:
        parts.append("\n<b>Historical references ({n}):</b>".format(n=len(resp.receipts)))
        for r in resp.receipts:
            outlet = escape(r.outlet or "unknown outlet")
            title = escape(_shorten(r.title, 120))
            sim = f"{r.similarity * 100:.0f}%"
            parts.append(
                f'• {r.date} — <a href="{escape(r.url)}">{title}</a>\n'
                f'  {outlet} · similarity {sim}'
            )

    parts.append(DISCLAIMER)
    return "\n".join(parts)


WELCOME = (
    "👋 Hi! I help identify recurring propaganda narratives in Telegram posts.\n\n"
    "<b>How to use:</b>\n"
    "• Send me a link to a public Telegram message: "
    "<code>https://t.me/channel_name/12345</code>\n"
    "• Or paste the message text directly.\n\n"
    "I'll match it against the <b>EUvsDisinfo</b> database of ~14,000 documented "
    "pro-Kremlin disinformation cases and show you similar historical references.\n\n"
    "<i>I don't decide what is or isn't true. I show you whether a message "
    "follows a pattern already documented by EU analysts. The interpretation "
    "is yours.</i>\n\n"
    "Commands: /check, /help, /about"
)

HELP = (
    "<b>Commands</b>\n"
    "/check &lt;url or text&gt; — analyze a message\n"
    "/delete_my_data — revoke consent and delete your bot data\n"
    "/about — project info and disclaimer\n"
    "/help — this message\n\n"
    "<b>Examples</b>\n"
    "<code>/check https://t.me/some_channel/12345</code>\n"
    "<code>/check Ukraine doesn't exist as a nation</code>\n\n"
    "You can also just send me a link or text without /check."
)

ABOUT = (
    "<b>About this bot</b>\n\n"
    "This bot matches incoming Telegram messages against the public "
    "<a href=\"https://euvsdisinfo.eu\">EUvsDisinfo</a> database — the official "
    "disinformation repository maintained by the European External Action Service.\n\n"
    "<b>What this bot is NOT</b>\n"
    "• Not a fact-checker.\n"
    "• Not a truth oracle.\n"
    "• Not a blocker — the bot never deletes or hides posts.\n\n"
    "<b>What it does</b>\n"
    "It flags whether a message follows a propaganda pattern already documented "
    "by EU analysts, and shows you the original case files. You decide what to do.\n\n"
    "Built for the DAAD East-West Partnership hackathon on Disinformation, AI, and Law.\n"
    "The bot is a research prototype and does not represent an official EU or EEAS position."
)
