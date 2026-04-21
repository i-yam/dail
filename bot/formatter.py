from __future__ import annotations
"""
bot/formatter.py
Telegram message formatting helpers.

All functions return plain strings with Telegram MarkdownV2 or HTML
(we use HTML mode throughout — much simpler to escape).
"""

from datetime import datetime


def _ts(iso: str) -> str:
    """Format an ISO timestamp into a short human-readable string."""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d %b %H:%M UTC")
    except Exception:
        return iso


def _conf_bar(confidence: float, length: int = 10) -> str:
    """Render a simple ASCII confidence bar."""
    filled = round(confidence * length)
    return "█" * filled + "░" * (length - filled)


# ── Single message alert ──────────────────────────────────────────────────────

def format_flag_alert(text: str, username: str | None, confidence: float, label: str, cluster_id: str | None) -> str:
    """
    Short inline alert posted immediately after a propaganda message is detected
    in watch mode.
    """
    user_str = f"@{username}" if username else "unknown user"
    cluster_str = f"  🗂 Cluster: <code>{cluster_id}</code>\n" if cluster_id else ""
    bar = _conf_bar(confidence)

    return (
        f"🚨 <b>PROPAGANDA DETECTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 From: {user_str}\n"
        f"🏷 Narrative: <b>{label}</b>\n"
        f"{cluster_str}"
        f"📊 Confidence: {bar} {confidence:.0%}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <i>\"{_trim(text, 200)}\"</i>"
    )


# ── /report ───────────────────────────────────────────────────────────────────

def format_report(rows: list) -> str:
    """
    Format a list of flagged-message DB rows into a full report.
    Each row must have: text, username, timestamp, narrative_label, confidence, cluster_id
    """
    if not rows:
        return (
            "✅ <b>No propaganda found</b>\n"
            "No flagged messages in this chat yet.\n"
            "Use /watch to start real-time monitoring."
        )

    lines = [
        f"📋 <b>PROPAGANDA REPORT</b>  ({len(rows)} hit{'s' if len(rows) != 1 else ''})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]

    for i, row in enumerate(rows, 1):
        user_str = f"@{row['username']}" if row["username"] else "unknown"
        cluster_str = f"🗂 <code>{row['cluster_id']}</code>  " if row["cluster_id"] else ""
        lines.append(
            f"<b>#{i}</b>  [{_ts(row['timestamp'])}]  {user_str}\n"
            f"🏷 <b>{row['narrative_label']}</b>  {cluster_str}({row['confidence']:.0%})\n"
            f"💬 <i>\"{_trim(row['text'], 120)}\"</i>\n"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━\nUse /cluster to see narrative groups.")
    return "\n".join(lines)


# ── /analyze single text ─────────────────────────────────────────────────────

def format_analyze_result(text: str, is_propaganda: bool, confidence: float, label: str, cluster_id: str | None) -> str:
    """Result card for an on-demand /analyze <text> check."""
    verdict = "🚨 <b>PROPAGANDA</b>" if is_propaganda else "✅ <b>CLEAN</b>"
    cluster_str = f"\n🗂 Cluster: <code>{cluster_id}</code>" if cluster_id else ""
    bar = _conf_bar(confidence)

    return (
        f"{verdict}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 Narrative: <b>{label}</b>{cluster_str}\n"
        f"📊 Confidence: {bar} {confidence:.0%}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Analysed text:\n<i>\"{_trim(text, 300)}\"</i>"
    )


# ── /cluster ──────────────────────────────────────────────────────────────────

def format_clusters(clusters: dict[str, list]) -> str:
    """
    Render a narrative cluster map.
    clusters = { cluster_key: [row, row, ...], ... }
    """
    if not clusters:
        return (
            "🗂 <b>No clusters yet.</b>\n"
            "Enable /watch and collect some messages first."
        )

    total = sum(len(v) for v in clusters.values())
    lines = [
        f"🗺 <b>NARRATIVE CLUSTER MAP</b>  ({len(clusters)} cluster{'s' if len(clusters) != 1 else ''}  ·  {total} hits)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]

    # Sort by frequency descending
    for cluster_key, rows in sorted(clusters.items(), key=lambda x: -len(x[1])):
        avg_conf = sum(r["confidence"] for r in rows) / len(rows)
        # Use the most common narrative_label in this cluster
        label_counts: dict[str, int] = {}
        for r in rows:
            label_counts[r["narrative_label"]] = label_counts.get(r["narrative_label"], 0) + 1
        top_label = max(label_counts, key=label_counts.__getitem__)

        bar = _conf_bar(avg_conf, length=8)
        lines.append(
            f"🏷 <b>{top_label}</b>\n"
            f"   🗂 <code>{cluster_key}</code>  ·  {len(rows)} hit{'s' if len(rows) != 1 else ''}  ·  avg {bar} {avg_conf:.0%}\n"
            f"   Latest: <i>\"{_trim(rows[-1]['text'], 80)}\"</i>\n"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ── /watch status ─────────────────────────────────────────────────────────────

def format_watch_on() -> str:
    return (
        "👁 <b>Watch mode ENABLED</b>\n"
        "I'll now monitor every message in this chat.\n"
        "Propaganda hits will be flagged immediately.\n\n"
        "Use /watch again to disable.  Use /report for a summary."
    )


def format_watch_off() -> str:
    return (
        "🔇 <b>Watch mode DISABLED</b>\n"
        "I've stopped monitoring this chat.\n"
        "Use /watch to re-enable.  Stored receipts still available via /report."
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _trim(text: str, max_len: int) -> str:
    """Trim text and add ellipsis if needed. Also escapes HTML chars."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if len(text) > max_len:
        return text[:max_len].rstrip() + "…"
    return text
