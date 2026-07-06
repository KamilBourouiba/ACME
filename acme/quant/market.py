"""Real market data via yfinance (no API key required) with in-memory quote cache."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from functools import partial
from typing import Any

from acme.config import settings

logger = logging.getLogger("acme.quant.market")


def _fetch_quotes_batch_sync(symbols: list[str]) -> list[dict]:
    """Fetch all symbols in one yfinance batch call (much faster than per-ticker)."""
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed — returning empty quotes")
        return []

    syms = [s.strip().upper() for s in symbols if s.strip()]
    if not syms:
        return []

    now = datetime.now(timezone.utc)
    results: list[dict] = []

    try:
        if len(syms) == 1:
            frames = {syms[0]: yf.download(syms[0], period="5d", progress=False, auto_adjust=True)}
        else:
            raw = yf.download(
                syms,
                period="5d",
                group_by="ticker",
                progress=False,
                threads=True,
                auto_adjust=True,
            )
            if raw.empty:
                raise ValueError("empty batch download")
            frames = {}
            if len(syms) == 1 or not isinstance(raw.columns, type(raw.columns)):
                frames[syms[0]] = raw
            else:
                for sym in syms:
                    try:
                        frames[sym] = raw[sym].dropna(how="all")
                    except (KeyError, TypeError):
                        continue

        for sym in syms:
            df = frames.get(sym)
            if df is None or df.empty:
                continue
            close = df["Close"].dropna()
            if close.empty:
                continue
            price = float(close.iloc[-1])
            prev = float(close.iloc[-2]) if len(close) > 1 else price
            change_pct = ((price - prev) / prev * 100) if prev else 0.0
            vol_series = df.get("Volume")
            volume = int(vol_series.dropna().iloc[-1]) if vol_series is not None and not vol_series.dropna().empty else 0
            results.append(
                {
                    "symbol": sym,
                    "price": round(price, 4),
                    "change_pct": round(change_pct, 3),
                    "volume": volume,
                    "market_cap": None,
                    "timestamp": now,
                }
            )
    except Exception as exc:
        logger.warning("Batch quote fetch failed, falling back per-symbol: %s", exc)
        return _fetch_quotes_sync(syms)

    # Preserve watchlist order; fill missing via fast_info fallback
    by_sym = {q["symbol"]: q for q in results}
    if len(by_sym) < len(syms):
        missing = [s for s in syms if s not in by_sym]
        for q in _fetch_quotes_sync(missing):
            by_sym[q["symbol"]] = q

    return [by_sym[s] for s in syms if s in by_sym]


def _fetch_quotes_sync(symbols: list[str]) -> list[dict]:
    try:
        import yfinance as yf
    except ImportError:
        return []

    results: list[dict] = []
    now = datetime.now(timezone.utc)
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
                    "timestamp": now,
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


class QuoteCache:
    """TTL cache with stale-while-revalidate for dashboard reads."""

    def __init__(self, ttl_sec: float = 60.0) -> None:
        self.ttl_sec = ttl_sec
        self._quotes: list[dict[str, Any]] = []
        self._symbols_key: tuple[str, ...] = ()
        self._fetched_at: datetime | None = None
        self._lock = asyncio.Lock()
        self._refreshing = False

    def _age_sec(self) -> float:
        if self._fetched_at is None:
            return float("inf")
        return (datetime.now(timezone.utc) - self._fetched_at).total_seconds()

    def _is_fresh(self) -> bool:
        return self._quotes and self._age_sec() < self.ttl_sec

    async def _refresh(self, symbols: list[str]) -> list[dict]:
        loop = asyncio.get_event_loop()
        quotes = await loop.run_in_executor(None, partial(_fetch_quotes_batch_sync, symbols))
        async with self._lock:
            self._quotes = quotes
            self._symbols_key = tuple(symbols)
            self._fetched_at = datetime.now(timezone.utc)
            self._refreshing = False
        return quotes

    async def get(self, symbols: list[str], *, force: bool = False) -> list[dict]:
        key = tuple(symbols)
        if not force and self._is_fresh() and self._symbols_key == key:
            return list(self._quotes)

        if not force and self._quotes and self._symbols_key == key:
            if not self._refreshing:
                self._refreshing = True
                asyncio.create_task(self._refresh(symbols))
            return list(self._quotes)

        return await self._refresh(symbols)

    async def warm(self, symbols: list[str]) -> None:
        try:
            await self._refresh(symbols)
            logger.info("Quote cache warmed (%d symbols)", len(symbols))
        except Exception:
            logger.exception("Quote cache warm failed")


quote_cache = QuoteCache(ttl_sec=float(settings.quant_quote_cache_sec))


async def fetch_quotes(symbols: list[str], *, force: bool = False) -> list[dict]:
    return await quote_cache.get(symbols, force=force)


async def fetch_bars(symbol: str, period: str = "5d") -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_fetch_bars_sync, symbol, period))


def _fetch_intraday_sync(symbol: str, interval: str = "5m", period: str = "1d") -> list[dict]:
    try:
        import yfinance as yf
    except ImportError:
        return []

    try:
        df = yf.Ticker(symbol.upper()).history(period=period, interval=interval)
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
        logger.warning("Intraday fetch failed for %s %s: %s", symbol, interval, exc)
        return []


def _fetch_intraday_batch_sync(symbols: list[str], interval: str = "5m") -> dict[str, list[dict]]:
    try:
        import yfinance as yf
    except ImportError:
        return {}

    syms = [s.strip().upper() for s in symbols if s.strip()]
    out: dict[str, list[dict]] = {}
    try:
        if len(syms) == 1:
            out[syms[0]] = _fetch_intraday_sync(syms[0], interval)
            return out
        raw = yf.download(
            syms,
            period="1d",
            interval=interval,
            group_by="ticker",
            progress=False,
            threads=True,
            auto_adjust=True,
        )
        if raw.empty:
            raise ValueError("empty intraday batch")
        for sym in syms:
            try:
                sub = raw[sym].dropna(how="all")
                bars = []
                for idx, row in sub.iterrows():
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
                if bars:
                    out[sym] = bars
            except (KeyError, TypeError, ValueError):
                continue
    except Exception as exc:
        logger.warning("Intraday batch failed: %s", exc)
        for sym in syms:
            if sym not in out:
                bars = _fetch_intraday_sync(sym, interval)
                if bars:
                    out[sym] = bars
    return out


async def fetch_intraday_bars(
    symbols: list[str],
    interval: str | None = None,
) -> dict[str, list[dict]]:
    iv = interval or settings.quant_bar_interval
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, partial(_fetch_intraday_batch_sync, symbols, iv)
    )


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
