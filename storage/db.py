from __future__ import annotations
"""
storage/db.py
SQLite database layer for the Propaganda Watchdog Bot.

Tables:
  - messages      : every message the bot has seen (while watch is active)
  - flagged       : messages classified as propaganda
  - watch_chats   : chats where real-time monitoring is enabled
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "bot.db"


def get_connection() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection with row_factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrency
    return conn


def init_db() -> None:
    """Create all tables on first run."""
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     INTEGER NOT NULL,
                user_id     INTEGER,
                username    TEXT,
                text        TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS flagged (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id      INTEGER NOT NULL REFERENCES messages(id),
                chat_id         INTEGER NOT NULL,
                narrative_label TEXT    NOT NULL,
                confidence      REAL    NOT NULL,
                cluster_id      TEXT,
                flagged_at      TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS watch_chats (
                chat_id     INTEGER PRIMARY KEY,
                enabled_at  TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
            CREATE INDEX IF NOT EXISTS idx_flagged_chat  ON flagged(chat_id);
            CREATE INDEX IF NOT EXISTS idx_flagged_cluster ON flagged(cluster_id);
        """)
    conn.close()
    logger.info("Database initialised at %s", DB_PATH)


# ── Message storage ──────────────────────────────────────────────────────────

def save_message(chat_id: int, user_id: int | None, username: str | None, text: str) -> int:
    """Insert a message and return its new row id."""
    conn = get_connection()
    ts = datetime.utcnow().isoformat()
    with conn:
        cur = conn.execute(
            "INSERT INTO messages (chat_id, user_id, username, text, timestamp) VALUES (?,?,?,?,?)",
            (chat_id, user_id, username, text, ts),
        )
        row_id = cur.lastrowid
    conn.close()
    return row_id


def get_recent_messages(chat_id: int, limit: int = 10) -> list[sqlite3.Row]:
    """Fetch the most recent `limit` messages for a chat."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT ?",
        (chat_id, limit),
    ).fetchall()
    conn.close()
    return list(reversed(rows))  # oldest first


# ── Flagged narrative storage ─────────────────────────────────────────────────

def save_flagged(
    message_id: int,
    chat_id: int,
    narrative_label: str,
    confidence: float,
    cluster_id: str | None,
) -> None:
    """Record a propaganda hit."""
    conn = get_connection()
    ts = datetime.utcnow().isoformat()
    with conn:
        conn.execute(
            """INSERT INTO flagged
               (message_id, chat_id, narrative_label, confidence, cluster_id, flagged_at)
               VALUES (?,?,?,?,?,?)""",
            (message_id, chat_id, narrative_label, confidence, cluster_id, ts),
        )
    conn.close()


def get_flagged_for_chat(chat_id: int, limit: int = 20) -> list[sqlite3.Row]:
    """Return the most recent flagged messages for a chat, newest first."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT f.*, m.text, m.username, m.timestamp
           FROM flagged f
           JOIN messages m ON f.message_id = m.id
           WHERE f.chat_id=?
           ORDER BY f.id DESC LIMIT ?""",
        (chat_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_clusters_for_chat(chat_id: int) -> dict[str, list[sqlite3.Row]]:
    """Group flagged messages by cluster_id (or narrative_label as fallback)."""
    rows = get_flagged_for_chat(chat_id, limit=200)
    clusters: dict[str, list] = {}
    for row in rows:
        key = row["cluster_id"] or row["narrative_label"]
        clusters.setdefault(key, []).append(row)
    return clusters


# ── Watch-mode management ─────────────────────────────────────────────────────

def enable_watch(chat_id: int) -> None:
    conn = get_connection()
    ts = datetime.utcnow().isoformat()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO watch_chats (chat_id, enabled_at) VALUES (?,?)",
            (chat_id, ts),
        )
    conn.close()


def disable_watch(chat_id: int) -> None:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM watch_chats WHERE chat_id=?", (chat_id,))
    conn.close()


def is_watch_enabled(chat_id: int) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM watch_chats WHERE chat_id=?", (chat_id,)
    ).fetchone()
    conn.close()
    return row is not None
