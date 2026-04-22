"""Simple persistent consent storage."""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
CONSENT_FILE = DATA_DIR / "consents.json"

_LOCK = RLock()


def _read_all() -> set[int]:
    if not CONSENT_FILE.exists():
        return set()
    try:
        payload = json.loads(CONSENT_FILE.read_text(encoding="utf-8"))
        users = payload.get("consented_user_ids", [])
        return {int(u) for u in users}
    except Exception:
        return set()


def _write_all(user_ids: set[int]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONSENT_FILE.with_suffix(".tmp")
    payload = {"consented_user_ids": sorted(user_ids)}
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONSENT_FILE)


def has_consent(user_id: int) -> bool:
    with _LOCK:
        return user_id in _read_all()


def grant_consent(user_id: int) -> None:
    with _LOCK:
        users = _read_all()
        users.add(user_id)
        _write_all(users)


def revoke_consent(user_id: int) -> None:
    with _LOCK:
        users = _read_all()
        users.discard(user_id)
        _write_all(users)
