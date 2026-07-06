"""Leverage, commissions, and carry costs for paper margin trading."""

from __future__ import annotations

from acme.config import settings
from acme.quant.symbols import is_crypto


def leverage_enabled() -> bool:
    return settings.quant_leverage_enabled


def leverage_for_symbol(symbol: str) -> float:
    if not settings.quant_leverage_enabled:
        return 1.0
    cap = max(settings.quant_max_leverage, 1.0)
    if is_crypto(symbol):
        return min(max(settings.quant_crypto_leverage, 1.0), cap)
    return min(max(settings.quant_equity_leverage, 1.0), cap)


def trade_commission(symbol: str, notional: float) -> float:
    if notional <= 0:
        return 0.0
    if is_crypto(symbol):
        return round(notional * settings.quant_crypto_taker_fee_bps / 10_000, 4)
    bps_fee = notional * settings.quant_equity_commission_bps / 10_000
    return round(max(bps_fee, settings.quant_equity_min_commission), 2)


def margin_required(notional: float, leverage: float) -> float:
    lev = max(leverage, 1.0)
    return round(notional / lev, 2)


def borrowed_from_cost(cost_basis: float, leverage: float) -> float:
    lev = max(leverage, 1.0)
    if lev <= 1.0:
        return 0.0
    return round(cost_basis * (1.0 - 1.0 / lev), 2)


def max_buy_notional(available_cash: float, symbol: str, leverage: float) -> float:
    """Largest notional affordable including commission."""
    if available_cash <= 0:
        return 0.0
    lev = max(leverage, 1.0)
    est = available_cash * lev
    for _ in range(24):
        fee = trade_commission(symbol, est)
        need = margin_required(est, lev) + fee
        if need <= available_cash:
            return round(est, 2)
        est = est * (available_cash / need) * 0.995
    return round(max(est, 0.0), 2)


def carry_cost(
    *,
    symbol: str,
    borrowed: float,
    notional: float,
    hours: float,
) -> float:
    if hours <= 0:
        return 0.0
    if is_crypto(symbol):
        base = notional
        apy = settings.quant_crypto_funding_apy
    else:
        base = borrowed
        apy = settings.quant_margin_interest_apy
    if base <= 0:
        return 0.0
    return round(base * (apy / 100.0) / (365.0 * 24.0) * hours, 4)
