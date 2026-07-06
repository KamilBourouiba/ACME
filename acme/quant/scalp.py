"""5-minute and sub-5m scalp signal engine."""

from __future__ import annotations

from typing import Any


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


def scalp_signal(
    symbol: str,
    bars: list[dict],
    *,
    momentum_threshold_pct: float = 0.06,
    min_bars: int = 4,
) -> dict[str, Any] | None:
    """
    Rule-based scalp signal from intraday bars.
    Returns entry signal dict or None.
    """
    if len(bars) < min_bars:
        return None

    mom_1 = compute_bar_momentum(bars, 1)
    mom_3 = compute_bar_momentum(bars, 3)
    last = bars[-1]
    price = last["close"]
    vwap = compute_vwap_proxy(bars)
    above_vwap = vwap is not None and price > vwap

    # Long scalp: 1-bar momentum + 3-bar trend aligned, price above VWAP proxy
    if mom_1 >= momentum_threshold_pct and mom_3 >= 0 and above_vwap:
        strength = min(abs(mom_1) / momentum_threshold_pct, 3.0) / 3.0
        return {
            "symbol": symbol,
            "side": "buy",
            "price": price,
            "confidence": round(0.45 + strength * 0.35, 2),
            "reasoning": (
                f"Scalp long: 5m +{mom_1:.2f}% (3-bar {mom_3:+.2f}%), "
                f"price ${price:.2f} above VWAP ${vwap:.2f}"
            ),
            "tags": ["scalp", "long", "momentum"],
            "mom_1": mom_1,
            "mom_3": mom_3,
        }

    # Exit signal for longs: momentum flipped negative
    if mom_1 <= -momentum_threshold_pct and mom_3 <= 0:
        return {
            "symbol": symbol,
            "side": "sell",
            "price": price,
            "confidence": round(0.5 + min(abs(mom_1) / momentum_threshold_pct, 2.0) * 0.2, 2),
            "reasoning": (
                f"Scalp exit: 5m {mom_1:.2f}% (3-bar {mom_3:+.2f}%), "
                f"momentum reversal"
            ),
            "tags": ["scalp", "exit", "momentum"],
            "mom_1": mom_1,
            "mom_3": mom_3,
        }

    return None


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
