"""Watchlist helpers — US equities vs Yahoo crypto pairs (e.g. BTC-USD)."""

from __future__ import annotations

from acme.config import settings

_CRYPTO_SUFFIX = "-USD"


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def is_crypto(symbol: str) -> bool:
    sym = normalize_symbol(symbol)
    return sym.endswith(_CRYPTO_SUFFIX) and len(sym) > len(_CRYPTO_SUFFIX)


def crypto_base(symbol: str) -> str:
    """BTC from BTC-USD."""
    sym = normalize_symbol(symbol)
    if is_crypto(sym):
        return sym[: -len(_CRYPTO_SUFFIX)]
    return sym


def equity_symbols() -> list[str]:
    return [normalize_symbol(s) for s in settings.quant_symbols.split(",") if s.strip()]


def crypto_symbols() -> list[str]:
    if not settings.quant_crypto_enabled:
        return []
    return [normalize_symbol(s) for s in settings.quant_crypto_symbols.split(",") if s.strip()]


def all_symbols() -> list[str]:
    return equity_symbols() + crypto_symbols()


def split_universe(symbols: list[str] | None = None) -> tuple[list[str], list[str]]:
    syms = symbols or all_symbols()
    eq = [s for s in syms if not is_crypto(s)]
    cr = [s for s in syms if is_crypto(s)]
    return eq, cr


def belief_matches_symbol(label: str, symbol: str) -> bool:
    upper = label.upper()
    sym = normalize_symbol(symbol)
    if sym in upper:
        return True
    if is_crypto(sym):
        base = crypto_base(sym)
        return base in upper
    return False


def intraday_period_for(symbols: list[str]) -> str:
    if any(is_crypto(s) for s in symbols):
        return settings.quant_crypto_intraday_period
    return settings.quant_intraday_period
