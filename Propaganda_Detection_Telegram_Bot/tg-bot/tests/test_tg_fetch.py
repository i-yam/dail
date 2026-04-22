"""Tests for URL parsing + HTML extraction. No network."""
from bot.tg_fetch import (
    FetchError,
    FetchFailure,
    _extract_message,
    looks_like_tg_url,
    parse_tg_url,
)


# Synthetic HTML in the same shape t.me/s/{channel}/{msg_id} renders.
# Structure verified via public sources + apify + dev.to guides.
SAMPLE_HTML = """
<html><body>
<div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message" data-post="rian_ru/12344">
        <div class="tgme_widget_message_text">Previous message content here.</div>
    </div>
</div>
<div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message" data-post="rian_ru/12345">
        <div class="tgme_widget_message_text">На Украине американские биолаборатории<br>разрабатывают биооружие против России.</div>
    </div>
</div>
<div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message" data-post="rian_ru/12346">
        <div class="tgme_widget_message_text">Next message.</div>
    </div>
</div>
</body></html>
"""


def test_parse_valid_public_url():
    r = parse_tg_url("https://t.me/rian_ru/12345")
    assert r == ("rian_ru", "12345")


def test_parse_valid_s_url():
    r = parse_tg_url("https://t.me/s/rian_ru/12345")
    assert r == ("rian_ru", "12345")


def test_parse_with_trailing_slash():
    r = parse_tg_url("https://t.me/rian_ru/12345/")
    assert r == ("rian_ru", "12345")


def test_parse_private_channel_fails_clearly():
    r = parse_tg_url("https://t.me/c/1234567890/555")
    assert isinstance(r, FetchFailure)
    assert r.error == FetchError.PRIVATE_CHANNEL


def test_parse_non_tg_url():
    r = parse_tg_url("https://google.com/search")
    assert isinstance(r, FetchFailure)
    assert r.error == FetchError.INVALID_URL


def test_parse_malformed():
    r = parse_tg_url("not a url at all")
    assert isinstance(r, FetchFailure)
    assert r.error == FetchError.INVALID_URL


def test_looks_like_tg_url():
    assert looks_like_tg_url("https://t.me/channel/1")
    assert looks_like_tg_url("http://t.me/channel/1")
    assert looks_like_tg_url("https://telegram.me/channel/1")
    assert not looks_like_tg_url("https://example.com")
    assert not looks_like_tg_url("some random text")


def test_extract_picks_right_message():
    txt = _extract_message(SAMPLE_HTML, "rian_ru", "12345")
    assert txt is not None
    assert "биолаборатории" in txt
    assert "Previous message" not in txt
    assert "Next message" not in txt


def test_extract_preserves_linebreaks():
    txt = _extract_message(SAMPLE_HTML, "rian_ru", "12345")
    assert "\n" in txt


def test_extract_case_insensitive_channel():
    txt = _extract_message(SAMPLE_HTML, "RIAN_RU", "12345")
    assert txt is not None
    assert "биолаборатории" in txt


def test_extract_missing_message():
    txt = _extract_message(SAMPLE_HTML, "rian_ru", "99999")
    assert txt is None


def test_extract_empty_text_message():
    html = """
    <div class="tgme_widget_message" data-post="ch/1">
        <!-- no .tgme_widget_message_text child, e.g. sticker post -->
    </div>
    """
    txt = _extract_message(html, "ch", "1")
    assert txt == ""


if __name__ == "__main__":
    import sys
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
            except AssertionError as e:
                print(f"  ✗ {name}: {e}")
                failed += 1
    print(f"\n{failed} failed" if failed else "\nall passed")
    sys.exit(1 if failed else 0)
