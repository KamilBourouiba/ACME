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


def round_trip_fee_pct(symbol: str) -> float:
    """Estimated round-trip commission as % of notional."""
    if is_crypto(symbol):
        return settings.quant_crypto_taker_fee_bps * 2.0 / 100.0
    return settings.quant_equity_commission_bps * 2.0 / 100.0


def funding_drag_pct(symbol: str, hold_sec: float, leverage: float = 1.0) -> float:
    """Estimated carry/funding drag as % of notional over hold time."""
    if hold_sec <= 0:
        return 0.0
    hours = hold_sec / 3600.0
    if is_crypto(symbol):
        apy = settings.quant_crypto_funding_apy
        return round(apy / 100.0 / (365.0 * 24.0) * hours * 100, 4)
    lev = max(leverage, 1.0)
    borrowed_frac = 0.0 if lev <= 1.0 else (1.0 - 1.0 / lev)
    apy = settings.quant_margin_interest_apy
    return round(apy / 100.0 / (365.0 * 24.0) * hours * borrowed_frac * 100, 4)


def min_entry_momentum_pct(symbol: str) -> float:
    """Minimum |momentum| required to open — must clear round-trip fees."""
    return round(round_trip_fee_pct(symbol) * settings.quant_min_entry_fee_multiple, 4)


def min_net_profit_pct(symbol: str, hold_sec: float = 0, leverage: float = 1.0) -> float:
    """Minimum net P&L % (after fees + estimated funding) to count as a win."""
    base = round_trip_fee_pct(symbol) * settings.quant_profit_fee_buffer
    return round(base + funding_drag_pct(symbol, hold_sec, leverage), 4)


def gross_for_net_profit(
    symbol: str,
    target_net_pct: float,
    hold_sec: float = 0,
    leverage: float = 1.0,
) -> float:
    """Gross price move % needed to achieve target_net_pct after costs."""
    return round(
        target_net_pct + round_trip_fee_pct(symbol) + funding_drag_pct(symbol, hold_sec, leverage),
        4,
    )


def net_pnl_pct_long(
    avg_cost: float,
    price: float,
    symbol: str,
    *,
    hold_sec: float = 0,
    leverage: float = 1.0,
) -> float:
    if avg_cost <= 0:
        return 0.0
    gross = (price - avg_cost) / avg_cost * 100
    return round(gross - round_trip_fee_pct(symbol) - funding_drag_pct(symbol, hold_sec, leverage), 4)


def net_pnl_pct_short(
    avg_cost: float,
    price: float,
    symbol: str,
    *,
    hold_sec: float = 0,
    leverage: float = 1.0,
) -> float:
    if avg_cost <= 0:
        return 0.0
    gross = (avg_cost - price) / avg_cost * 100
    return round(gross - round_trip_fee_pct(symbol) - funding_drag_pct(symbol, hold_sec, leverage), 4)


def effective_take_profit_pct(symbol: str, base_tp_pct: float, hold_sec: float = 0, leverage: float = 1.0) -> float:
    """Take-profit floor that clears fees, funding, and buffer."""
    floor = gross_for_net_profit(
        symbol,
        min_net_profit_pct(symbol, hold_sec, leverage) * 0.5,
        hold_sec,
        leverage,
    )
    return max(base_tp_pct, floor)


def min_profit_take_pct(symbol: str, hold_sec: float = 0, leverage: float = 1.0) -> float:
    configured = (
        settings.quant_crypto_profit_take_min_pct
        if is_crypto(symbol)
        else settings.quant_profit_take_min_pct
    )
    floor = gross_for_net_profit(
        symbol,
        min_net_profit_pct(symbol, hold_sec, leverage),
        hold_sec,
        leverage,
    )
    return max(configured, floor)


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
