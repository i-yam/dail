"""
Pipeline tracing. Prints pretty blocks to stdout at each stage so you can
watch a request flow through bot → fetch → model → reply in real time.

Turn off by setting env TRACE=0.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

ENABLED = os.getenv("TRACE", "1") != "0"
HR = "─" * 72


@dataclass
class Trace:
    """One request's trace. Build it up as the request flows through."""
    user_id: int
    username: str | None
    chat_type: str
    raw_input: str
    t_start: float

    @classmethod
    def start(cls, *, user_id: int, username: str | None, chat_type: str, raw: str) -> "Trace":
        t = cls(
            user_id=user_id,
            username=username or "",
            chat_type=chat_type,
            raw_input=raw,
            t_start=time.monotonic(),
        )
        if not ENABLED:
            return t
        user = f"@{t.username}" if t.username else f"id={t.user_id}"
        print()
        print(HR)
        print(f"📥 INCOMING  user={user}  chat={t.chat_type}")
        print(f"   raw: {_truncate(raw, 120)}")
        print(HR)
        return t

    def step(self, title: str) -> None:
        if ENABLED:
            print(f"\n▸ {title}")

    def kv(self, label: str, value: Any) -> None:
        if ENABLED:
            print(f"   {label:<14}{value}")

    def ok(self, msg: str) -> None:
        if ENABLED:
            print(f"   ✓ {msg}")

    def fail(self, msg: str) -> None:
        if ENABLED:
            print(f"   ✗ {msg}")

    def text_block(self, title: str, text: str, max_lines: int = 10) -> None:
        if not ENABLED:
            return
        print(f"\n   {title}")
        lines = text.splitlines() or [text]
        for line in lines[:max_lines]:
            print(f"   │ {_truncate(line, 110)}")
        if len(lines) > max_lines:
            print(f"   │ ... (+{len(lines) - max_lines} more lines)")

    def json_block(self, title: str, payload: dict) -> None:
        if not ENABLED:
            return
        print(f"\n   {title}")
        dumped = json.dumps(payload, indent=2, ensure_ascii=False)
        for line in dumped.splitlines():
            print(f"   │ {_truncate(line, 110)}")

    def finish(self, verdict: str) -> None:
        if not ENABLED:
            return
        elapsed_ms = (time.monotonic() - self.t_start) * 1000
        print()
        print(f"💬 REPLY SENT  verdict={verdict}  total={elapsed_ms:.0f}ms")
        print(HR)


def _truncate(s: str, n: int) -> str:
    s = (s or "").replace("\r", "")
    return s if len(s) <= n else s[: n - 1] + "…"