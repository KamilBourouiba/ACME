"""US equity session detection for automatic scalp scheduling."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
_OPEN = time(9, 30)
_CLOSE = time(16, 0)


def us_market_session(now: datetime | None = None) -> dict:
    """
    Return US regular session state (Mon–Fri 9:30–16:00 ET).
    """
    now = now or datetime.now(_ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    else:
        now = now.astimezone(_ET)

    wd = now.weekday()  # 0=Mon
    if wd >= 5:
        return {
            "open": False,
            "status": "weekend",
            "label": "Market closed (weekend)",
            "next_open_et": _next_open(now).isoformat(),
        }

    t = now.time()
    if t < _OPEN:
        return {
            "open": False,
            "status": "pre_market",
            "label": "Pre-market — opens 9:30 ET",
            "next_open_et": now.replace(hour=9, minute=30, second=0, microsecond=0).isoformat(),
        }
    if t >= _CLOSE:
        nxt = _next_open(now)
        return {
            "open": False,
            "status": "after_hours",
            "label": "After hours — closed 16:00 ET",
            "next_open_et": nxt.isoformat(),
        }

    close_at = now.replace(hour=16, minute=0, second=0, microsecond=0)
    mins_left = int((close_at - now).total_seconds() // 60)
    return {
        "open": True,
        "status": "open",
        "label": f"Market open · {mins_left}m to close",
        "next_open_et": None,
    }


def _next_open(now: datetime) -> datetime:
    """Next 9:30 ET on a weekday."""
    candidate = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now.weekday() < 5 and now.time() < _OPEN:
        return candidate
    candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate.replace(hour=9, minute=30, second=0, microsecond=0)


def cycle_interval_sec(session: dict, open_sec: int, closed_sec: int) -> int:
    if session.get("crypto_active") or session.get("equities_open"):
        return open_sec
    return closed_sec


def quant_trading_session(
    *,
    crypto_enabled: bool = True,
    now: datetime | None = None,
) -> dict:
    """Combined session: crypto 24/7 + US equities regular hours."""
    us = us_market_session(now)
    crypto_on = bool(crypto_enabled)

    if crypto_on and us["open"]:
        label = "Crypto 24/7 · US equities open"
        status = "full"
    elif crypto_on:
        label = f"Crypto 24/7 · equities closed ({us['status']})"
        status = "crypto_only"
    else:
        label = us["label"]
        status = us["status"]

    return {
        "open": us["open"] or crypto_on,
        "equities_open": us["open"],
        "crypto_active": crypto_on,
        "status": status,
        "label": label,
        "us_status": us["status"],
        "next_open_et": us.get("next_open_et"),
    }
