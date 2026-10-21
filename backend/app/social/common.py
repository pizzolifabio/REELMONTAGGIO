import secrets
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlmodel import select

from ..db import session_scope
from ..models import Account, now


class SocialError(RuntimeError):
    pass


def check(r: httpx.Response) -> dict[str, Any]:
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text[:500]}
    # TikTok risponde sempre con {"error": {"code": "ok"}} anche in caso di successo
    err = data.get("error") if isinstance(data, dict) else None
    if r.status_code >= 400 or (isinstance(err, dict) and err.get("code") not in (None, "ok")):
        raise SocialError(f"HTTP {r.status_code}: {err or data}")
    return data


def get_account(platform: str) -> Account | None:
    with session_scope() as s:
        return s.exec(select(Account).where(Account.platform == platform)).first()


def save_account(platform: str, **fields) -> Account:
    with session_scope() as s:
        acc = s.exec(select(Account).where(Account.platform == platform)).first() or Account(platform=platform)
        for k, v in fields.items():
            setattr(acc, k, v)
        acc.connected_at = now()
        s.add(acc)
        s.commit()
        s.refresh(acc)
        return acc


def expires_in(seconds: int | float | None) -> datetime | None:
    return now() + timedelta(seconds=int(seconds)) if seconds else None


def needs_refresh(acc: Account, margin: timedelta = timedelta(minutes=5)) -> bool:
    return acc.expires_at is not None and acc.expires_at - margin <= now()


# stato OAuth in memoria (uso personale, un solo processo)
_states: dict[str, tuple[str, float, dict]] = {}


def new_state(platform: str, **extra) -> str:
    state = secrets.token_urlsafe(16)
    _states[state] = (platform, time.time(), extra)
    return state


def pop_state(state: str, platform: str) -> dict:
    entry = _states.pop(state, None)
    if not entry or entry[0] != platform or time.time() - entry[1] > 900:
        raise SocialError("Stato OAuth non valido o scaduto: riprova a collegare l'account")
    return entry[2]
