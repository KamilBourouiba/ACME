"""Real market data via yfinance (no API key required)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from functools import partial

logger = logging.getLogger("acme.quant.market")


def _fetch_quotes_sync(symbols: list[str]) -> list[dict]:
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed — returning empty quotes")
        return []

    results: list[dict] = []
    for sym in symbols:
        sym = sym.strip().upper()
        if not sym:
            continue
        try:
            ticker = yf.Ticker(sym)
            info = ticker.fast_info
            price = float(getattr(info, "last_price", 0) or 0)
            prev = float(getattr(info, "previous_close", 0) or price)
            change_pct = ((price - prev) / prev * 100) if prev else 0.0
            results.append(
                {
                    "symbol": sym,
                    "price": round(price, 4),
                    "change_pct": round(change_pct, 3),
                    "volume": int(getattr(info, "last_volume", 0) or 0),
                    "market_cap": float(getattr(info, "market_cap", 0) or 0) or None,
                    "timestamp": datetime.now(timezone.utc),
                }
            )
        except Exception as exc:
            logger.warning("Quote fetch failed for %s: %s", sym, exc)
    return results


def _fetch_bars_sync(symbol: str, period: str = "5d") -> list[dict]:
    try:
        import yfinance as yf
    except ImportError:
        return []

    try:
        df = yf.Ticker(symbol.upper()).history(period=period)
        if df.empty:
            return []
        bars = []
        for idx, row in df.iterrows():
            bars.append(
                {
                    "date": idx.isoformat(),
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row["Volume"]),
                }
            )
        return bars
    except Exception as exc:
        logger.warning("Bar fetch failed for %s: %s", symbol, exc)
        return []


async def fetch_quotes(symbols: list[str]) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_fetch_quotes_sync, symbols))


async def fetch_bars(symbol: str, period: str = "5d") -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_fetch_bars_sync, symbol, period))


def format_quote_experience(quote: dict) -> str:
    sym = quote["symbol"]
    price = quote["price"]
    chg = quote["change_pct"]
    vol = quote.get("volume") or 0
    sign = "+" if chg >= 0 else ""
    return f"{sym} ${price:.2f} ({sign}{chg:.2f}%), volume {vol:,}"


def format_bar_summary(symbol: str, bars: list[dict]) -> str:
    if not bars:
        return f"{symbol}: no recent bar data"
    last = bars[-1]
    first = bars[0]
    ret = ((last["close"] - first["close"]) / first["close"] * 100) if first["close"] else 0
    sign = "+" if ret >= 0 else ""
    return (
        f"{symbol} 5d: ${last['close']:.2f} ({sign}{ret:.2f}%), "
        f"range ${min(b['low'] for b in bars):.2f}–${max(b['high'] for b in bars):.2f}"
    )
