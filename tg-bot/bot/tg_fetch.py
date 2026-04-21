"""
Fetch a single Telegram message via the public web preview at
    https://t.me/s/{channel}/{msg_id}

This endpoint renders server-side HTML for any *public* channel without
authentication. The page shows a window of messages around the requested
id — we find the specific one by the `data-post="<channel>/<id>"` attribute.

Fails cleanly with a typed error when the URL is private, the channel
doesn't exist, or the message has no text (e.g. sticker-only post).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

PREVIEW_URL = "https://t.me/s/{channel}/{msg_id}"
FETCH_TIMEOUT_S = 12
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Public message URL:  https://t.me/<channel>/<id>   or   /s/<channel>/<id>
# Private channel URL: https://t.me/c/<internal_id>/<msg_id>   <- NOT supported
_URL_RE = re.compile(
    r"^https?://t\.me/(?:s/)?(?P<channel>[A-Za-z0-9_]{3,})/(?P<msg_id>\d+)/?$"
)
_PRIVATE_RE = re.compile(r"^https?://t\.me/c/\d+/\d+/?$")


class FetchError(str, Enum):
    INVALID_URL = "invalid_url"
    PRIVATE_CHANNEL = "private_channel"
    CHANNEL_NOT_FOUND = "channel_not_found"
    MESSAGE_NOT_FOUND = "message_not_found"
    NO_TEXT_CONTENT = "no_text_content"
    FETCH_FAILED = "fetch_failed"


@dataclass
class FetchedMessage:
    channel: str
    message_id: str
    text: str
    source_url: str


@dataclass
class FetchFailure:
    error: FetchError
    hint: str  # user-facing message


def parse_tg_url(url: str) -> tuple[str, str] | FetchFailure:
    """Extract (channel, msg_id) from a t.me URL or return a typed failure."""
    url = url.strip()
    if _PRIVATE_RE.match(url):
        return FetchFailure(
            FetchError.PRIVATE_CHANNEL,
            "This looks like a private channel link (t.me/c/...). "
            "I can only read public channels. Paste the message text instead.",
        )
    m = _URL_RE.match(url)
    if not m:
        return FetchFailure(
            FetchError.INVALID_URL,
            "That doesn't look like a Telegram message link. "
            "Expected format: https://t.me/<channel>/<message_id>",
        )
    return m.group("channel"), m.group("msg_id")


def _extract_message(html: str, channel: str, msg_id: str) -> str | None:
    """Pick the specific message by its data-post attribute; return its text."""
    soup = BeautifulSoup(html, "html.parser")
    target = f"{channel}/{msg_id}"
    # case-insensitive: channels in URLs are case-insensitive on telegram's side
    for msg in soup.select(".tgme_widget_message"):
        data_post = msg.get("data-post", "")
        if data_post.lower() == target.lower():
            text_el = msg.select_one(".tgme_widget_message_text")
            if not text_el:
                return ""
            # preserve line breaks, strip tags
            for br in text_el.find_all("br"):
                br.replace_with("\n")
            return text_el.get_text("\n", strip=False).strip()
    return None


async def fetch_message(url: str) -> FetchedMessage | FetchFailure:
    """Return extracted text for a public t.me message URL, or a FetchFailure."""
    parsed = parse_tg_url(url)
    if isinstance(parsed, FetchFailure):
        return parsed
    channel, msg_id = parsed

    preview_url = PREVIEW_URL.format(channel=channel, msg_id=msg_id)
    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_S, follow_redirects=True) as c:
            resp = await c.get(preview_url, headers=BROWSER_HEADERS)
    except httpx.RequestError as e:
        return FetchFailure(
            FetchError.FETCH_FAILED,
            f"Couldn't reach Telegram preview service: {e.__class__.__name__}. Try again.",
        )

    if resp.status_code == 404:
        return FetchFailure(
            FetchError.CHANNEL_NOT_FOUND,
            f"Channel @{channel} doesn't exist or has no web preview.",
        )
    if resp.status_code != 200:
        return FetchFailure(
            FetchError.FETCH_FAILED,
            f"Telegram returned HTTP {resp.status_code}.",
        )

    text = _extract_message(resp.text, channel, msg_id)
    if text is None:
        return FetchFailure(
            FetchError.MESSAGE_NOT_FOUND,
            f"Message {msg_id} not found in @{channel}. It may have been deleted.",
        )
    if not text.strip():
        return FetchFailure(
            FetchError.NO_TEXT_CONTENT,
            "That message has no text (probably media-only). "
            "Paste any text from the post instead.",
        )

    return FetchedMessage(
        channel=channel,
        message_id=msg_id,
        text=text,
        source_url=f"https://t.me/{channel}/{msg_id}",
    )


def looks_like_tg_url(s: str) -> bool:
    """Quick check without parsing — for routing in handlers."""
    try:
        host = urlparse(s.strip()).netloc.lower()
    except ValueError:
        return False
    return host in ("t.me", "telegram.me")
