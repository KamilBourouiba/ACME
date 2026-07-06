"""5-minute and sub-5m scalp signal engine."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from acme.config import settings


def compute_bar_momentum(bars: list[dict], lookback: int = 1) -> float:
    """Percent change over `lookback` completed bars."""
    if len(bars) <= lookback:
        return 0.0
    prev_close = bars[-(lookback + 1)]["close"]
    last_close = bars[-1]["close"]
    if not prev_close:
        return 0.0
    return (last_close - prev_close) / prev_close * 100


def compute_vwap_proxy(bars: list[dict], n: int = 6) -> float | None:
    """Volume-weighted average price over last n bars."""
    chunk = bars[-n:] if len(bars) >= n else bars
    if not chunk:
        return None
    vol = sum(b.get("volume", 0) for b in chunk)
    if vol <= 0:
        return sum(b["close"] for b in chunk) / len(chunk)
    return sum(b["close"] * b.get("volume", 0) for b in chunk) / vol


def bar_age_minutes(bars: list[dict]) -> float:
    if not bars:
        return float("inf")
    raw = bars[-1].get("date", "")
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() / 60
    except (ValueError, TypeError):
        return float("inf")


def bar_interval_minutes(interval: str | None = None) -> float:
    raw = (interval or settings.quant_bar_interval).strip().lower()
    if raw.endswith("m"):
        return float(raw[:-1] or 5)
    if raw.endswith("h"):
        return float(raw[:-1] or 1) * 60
    return 5.0


def completed_bars(bars: list[dict], interval_min: float | None = None) -> list[dict]:
    """Drop the in-progress candle — signals use only completed bars."""
    if len(bars) <= 1:
        return bars
    iv = interval_min if interval_min is not None else bar_interval_minutes()
    if bar_age_minutes(bars) < iv:
        return bars[:-1]
    return bars


def bars_are_fresh(bars: list[dict], max_age_min: float = 12.0) -> bool:
    """True if the latest bar is recent enough to trade on."""
    return bar_age_minutes(bars) <= max_age_min


def adaptive_momentum_threshold(
    intraday: dict[str, list[dict]],
    base: float,
    *,
    floor: float = 0.02,
) -> float:
    """Scale threshold to current watchlist volatility."""
    moms: list[float] = []
    for bars in intraday.values():
        if len(bars) >= 2:
            moms.append(abs(compute_bar_momentum(bars, 1)))
    if not moms:
        return base
    median = sorted(moms)[len(moms) // 2]
    adaptive = max(floor, min(base, median * 0.85))
    return round(adaptive, 4)


def is_actionable_belief(label: str) -> bool:
    """Skip trivial price/volume observation beliefs for trade linkage."""
    if "-[observed_with]->" not in label:
        return True
    rhs = label.split("->", 1)[-1].strip()
    if re.match(r"^[\$]?[\d,\.\+%]+$", rhs):
        return False
    if re.match(r"^[\d,]+$", rhs.replace(",", "")):
        return False
    return True


def scalp_signal(
    symbol: str,
    bars: list[dict],
    *,
    momentum_threshold_pct: float = 0.06,
    min_momentum_pct: float = 0.0,
    min_bars: int = 3,
    require_fresh: bool = True,
    max_bar_age_min: float = 12.0,
) -> dict[str, Any] | None:
    """
    Rule-based scalp signal from intraday bars.
    Returns entry signal dict or None.
    """
    bars = completed_bars(bars)
    if len(bars) < min_bars:
        return None
    if require_fresh and not bars_are_fresh(bars, max_bar_age_min):
        return None

    threshold = max(momentum_threshold_pct, min_momentum_pct)
    mom_1 = compute_bar_momentum(bars, 1)
    mom_3 = compute_bar_momentum(bars, 3)
    last = bars[-1]
    price = last["close"]
    vwap = compute_vwap_proxy(bars)
    above_vwap = vwap is not None and price > vwap
    below_vwap = vwap is not None and price < vwap
    strong = abs(mom_1) >= threshold * 1.4

    # Long scalp: momentum + trend; VWAP optional on strong impulse
    if mom_1 >= threshold and mom_3 >= -0.02 and (above_vwap or strong):
        strength = min(abs(mom_1) / threshold, 3.0) / 3.0
        return {
            "symbol": symbol,
            "side": "buy",
            "price": price,
            "confidence": round(0.45 + strength * 0.35, 2),
            "reasoning": (
                f"Scalp long: 5m +{mom_1:.2f}% (3-bar {mom_3:+.2f}%), "
                f"price ${price:.2f}" + (f" above VWAP ${vwap:.2f}" if above_vwap and vwap else "")
            ),
            "tags": ["scalp", "long", "momentum"],
            "mom_1": mom_1,
            "mom_3": mom_3,
        }

    # Bearish: close longs or open shorts (service routes by position)
    if mom_1 <= -threshold and mom_3 <= 0.02 and (below_vwap or strong):
        strength = min(abs(mom_1) / threshold, 3.0) / 3.0
        return {
            "symbol": symbol,
            "side": "sell",
            "price": price,
            "confidence": round(0.45 + strength * 0.35, 2),
            "reasoning": (
                f"Scalp bearish: 5m {mom_1:.2f}% (3-bar {mom_3:+.2f}%), "
                f"price ${price:.2f}" + (f" below VWAP ${vwap:.2f}" if below_vwap and vwap else "")
            ),
            "tags": ["scalp", "bearish", "momentum"],
            "mom_1": mom_1,
            "mom_3": mom_3,
        }

    return None


def profit_exit_signal(
    symbol: str,
    bars: list[dict],
    *,
    position_side: str,
    entry_price: float,
    momentum_threshold_pct: float,
    min_profit_pct: float,
    momentum_frac: float | None = None,
    hold_sec: float = 0,
    leverage: float = 1.0,
) -> dict[str, Any] | None:
    """Close a winning position when momentum fades (softer threshold than entry)."""
    bars = completed_bars(bars)
    if len(bars) < 3 or entry_price <= 0:
        return None

    from acme.quant.fees import min_net_profit_pct, net_pnl_pct_long, net_pnl_pct_short

    frac = momentum_frac if momentum_frac is not None else settings.quant_profit_exit_momentum_frac
    mom_1 = compute_bar_momentum(bars, 1)
    price = bars[-1]["close"]
    fade_thresh = momentum_threshold_pct * frac
    min_net = min_net_profit_pct(symbol, hold_sec, leverage)

    if position_side == "long":
        gross = (price - entry_price) / entry_price * 100
        net = net_pnl_pct_long(entry_price, price, symbol, hold_sec=hold_sec, leverage=leverage)
        if net >= min_net and gross >= min_profit_pct and mom_1 <= -fade_thresh:
            return {
                "symbol": symbol,
                "side": "sell",
                "price": price,
                "confidence": 0.72,
                "reasoning": (
                    f"Profit take net +{net:.2f}% (gross +{gross:.2f}%) on fade "
                    f"(5m {mom_1:.2f}%)"
                ),
                "tags": ["scalp", "profit_take", "long"],
                "mom_1": mom_1,
            }

    if position_side == "short":
        gross = (entry_price - price) / entry_price * 100
        net = net_pnl_pct_short(entry_price, price, symbol, hold_sec=hold_sec, leverage=leverage)
        if net >= min_net and gross >= min_profit_pct and mom_1 >= fade_thresh:
            return {
                "symbol": symbol,
                "side": "buy",
                "price": price,
                "confidence": 0.72,
                "reasoning": (
                    f"Short profit take net +{net:.2f}% (gross +{gross:.2f}%) on fade "
                    f"(5m +{mom_1:.2f}%)"
                ),
                "tags": ["scalp", "profit_take", "short"],
                "mom_1": mom_1,
            }

    return None


def scan_scalp_signals(
    intraday: dict[str, list[dict]],
    *,
    momentum_threshold_pct: float,
    min_momentum_by_symbol: dict[str, float] | None = None,
    min_bars: int = 3,
    require_fresh: bool = True,
    max_bar_age_min: float = 12.0,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    mins = min_momentum_by_symbol or {}
    for sym, bars in intraday.items():
        sig = scalp_signal(
            sym,
            bars,
            momentum_threshold_pct=momentum_threshold_pct,
            min_momentum_pct=mins.get(sym, mins.get(sym.upper(), 0.0)),
            min_bars=min_bars,
            require_fresh=require_fresh,
            max_bar_age_min=max_bar_age_min,
        )
        if sig:
            signals.append(sig)
    return signals


def format_scalp_experience(symbol: str, bars: list[dict], interval: str = "5m") -> str:
    if len(bars) < 2:
        return f"{symbol} {interval}: insufficient intraday data"
    last = bars[-1]
    mom = compute_bar_momentum(bars, 1)
    mom3 = compute_bar_momentum(bars, 3)
    sign = "+" if mom >= 0 else ""
    return (
        f"{symbol} {interval} ${last['close']:.2f} ({sign}{mom:.2f}% last bar, "
        f"{mom3:+.2f}% 3-bar), vol {last.get('volume', 0):,}"
    )


def rank_scalp_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strongest momentum signals first."""
    return sorted(signals, key=lambda s: abs(s.get("mom_1", 0)), reverse=True)


def intraday_last_prices(intraday: dict[str, list[dict]]) -> dict[str, float]:
    """Last bar close per symbol from intraday OHLCV."""
    out: dict[str, float] = {}
    for sym, bars in intraday.items():
        if bars:
            out[sym.upper()] = float(bars[-1]["close"])
    return out


def merge_mark_prices(
    symbols: list[str],
    intraday: dict[str, list[dict]],
    daily_prices: dict[str, float],
) -> dict[str, float]:
    """Mark and fill at intraday last close when available; else daily quote."""
    merged = {s.upper(): daily_prices[s] for s in daily_prices}
    for sym, px in intraday_last_prices(intraday).items():
        merged[sym] = px
    for sym in symbols:
        su = sym.upper()
        if su not in merged and su in daily_prices:
            merged[su] = daily_prices[su]
    return merged


def quotes_from_intraday(
    symbols: list[str],
    intraday: dict[str, list[dict]],
    daily_quotes: list[dict],
) -> list[dict]:
    """Build quote rows for dashboard — intraday 5m when available."""
    from datetime import datetime, timezone

    daily_by_sym = {q["symbol"]: q for q in daily_quotes}
    now = datetime.now(timezone.utc)
    rows: list[dict] = []
    for sym in symbols:
        su = sym.upper()
        bars = intraday.get(su) or intraday.get(sym) or []
        if bars:
            last = bars[-1]
            prev = bars[-2]["close"] if len(bars) > 1 else last["close"]
            chg = ((last["close"] - prev) / prev * 100) if prev else 0.0
            rows.append(
                {
                    "symbol": su,
                    "price": round(float(last["close"]), 4),
                    "change_pct": round(chg, 3),
                    "volume": int(last.get("volume") or 0),
                    "market_cap": daily_by_sym.get(su, {}).get("market_cap"),
                    "timestamp": now,
                }
            )
        elif su in daily_by_sym:
            rows.append(daily_by_sym[su])
    return rows
