"""Scalp exit rules — TP, SL, trailing stop, breakeven, max hold, ROE caps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from acme.config import settings
from acme.quant.fees import (
    effective_take_profit_pct,
    gross_for_net_profit,
    min_net_profit_pct,
    net_pnl_pct_long,
    net_pnl_pct_short,
)
from acme.quant.symbols import is_crypto


@dataclass
class ExitState:
    peak_price: float
    stop_floor: float | None = None


@dataclass
class ExitDecision:
    reason: str | None
    state: ExitState


def tp_sl_for_symbol(symbol: str) -> tuple[float, float]:
    if is_crypto(symbol):
        return (
            settings.quant_crypto_take_profit_pct,
            settings.quant_crypto_stop_loss_pct,
        )
    return (
        settings.quant_scalp_take_profit_pct,
        settings.quant_scalp_stop_loss_pct,
    )


def max_hold_for_symbol(symbol: str) -> int:
    if is_crypto(symbol):
        return settings.quant_crypto_max_hold_sec
    return settings.quant_scalp_max_hold_sec


def evaluate_exit(
    *,
    symbol: str,
    avg_cost: float,
    price: float,
    peak_price: float | None,
    stop_floor: float | None,
    leverage: float,
    opened_at: datetime,
    now: datetime,
    quantity: float = 0.0,
) -> ExitDecision:
    if avg_cost <= 0:
        return ExitDecision(None, ExitState(peak_price or price, stop_floor))

    is_short = quantity < 0
    lev = max(leverage, 1.0)
    hold_sec = max(0.0, (now - opened_at).total_seconds())

    if is_short:
        return _evaluate_short_exit(
            symbol=symbol,
            avg_cost=avg_cost,
            price=price,
            peak_price=peak_price,
            stop_floor=stop_floor,
            leverage=lev,
            hold_sec=hold_sec,
        )

    return _evaluate_long_exit(
        symbol=symbol,
        avg_cost=avg_cost,
        price=price,
        peak_price=peak_price,
        stop_floor=stop_floor,
        leverage=lev,
        hold_sec=hold_sec,
    )


def _evaluate_long_exit(
    *,
    symbol: str,
    avg_cost: float,
    price: float,
    peak_price: float | None,
    stop_floor: float | None,
    leverage: float,
    hold_sec: float,
) -> ExitDecision:
    peak = max(peak_price or avg_cost, price)
    state = ExitState(peak_price=peak, stop_floor=stop_floor)

    pnl_pct = (price - avg_cost) / avg_cost * 100
    net_pct = net_pnl_pct_long(avg_cost, price, symbol, hold_sec=hold_sec, leverage=leverage)
    roe_pct = pnl_pct * leverage
    min_net = min_net_profit_pct(symbol, hold_sec, leverage)
    tp_pct, sl_pct = tp_sl_for_symbol(symbol)
    tp_pct = effective_take_profit_pct(symbol, tp_pct, hold_sec, leverage)

    if (
        settings.quant_scalp_breakeven_trigger_pct > 0
        and net_pct >= min_net
        and pnl_pct >= settings.quant_scalp_breakeven_trigger_pct
        and (state.stop_floor is None or state.stop_floor < avg_cost)
    ):
        lock_gross = gross_for_net_profit(symbol, min_net, hold_sec, leverage)
        state.stop_floor = avg_cost * (1 + lock_gross / 100)

    if pnl_pct >= tp_pct and net_pct >= min_net:
        return ExitDecision(
            f"Take profit net +{net_pct:.2f}% (gross +{pnl_pct:.2f}%, ROE {roe_pct:+.2f}%)",
            state,
        )

    if settings.quant_leverage_enabled and leverage > 1.0:
        if roe_pct >= settings.quant_scalp_tp_roe_pct and net_pct >= min_net:
            return ExitDecision(
                f"ROE take profit net +{net_pct:.2f}% (ROE {roe_pct:+.2f}%)",
                state,
            )
        if roe_pct <= -settings.quant_scalp_sl_roe_pct:
            return ExitDecision(
                f"ROE stop {roe_pct:.2f}% ({pnl_pct:+.2f}% @ {leverage:.0f}x)",
                state,
            )

    if state.stop_floor is not None and price <= state.stop_floor:
        if net_pct >= min_net:
            return ExitDecision(
                f"Profit lock net +{net_pct:.2f}% @ ${price:.2f}",
                state,
            )

    if pnl_pct <= -sl_pct:
        return ExitDecision(
            f"Stop loss {pnl_pct:.2f}% (ROE {roe_pct:+.2f}%)",
            state,
        )

    if peak > avg_cost and settings.quant_scalp_trail_stop_pct > 0:
        trail_drop = (peak - price) / peak * 100
        if trail_drop >= settings.quant_scalp_trail_stop_pct and net_pct >= min_net:
            return ExitDecision(
                f"Trailing stop net +{net_pct:.2f}% (-{trail_drop:.2f}% from peak)",
                state,
            )

    max_hold = max_hold_for_symbol(symbol)
    if hold_sec >= max_hold:
        return ExitDecision(
            f"Max hold {int(hold_sec)}s (net {net_pct:+.2f}%)",
            state,
        )

    return ExitDecision(None, state)


def _evaluate_short_exit(
    *,
    symbol: str,
    avg_cost: float,
    price: float,
    peak_price: float | None,
    stop_floor: float | None,
    leverage: float,
    hold_sec: float,
) -> ExitDecision:
    """Short exits — peak_price tracks the trough (best price for the short)."""
    trough = min(peak_price or avg_cost, price)
    state = ExitState(peak_price=trough, stop_floor=stop_floor)

    pnl_pct = (avg_cost - price) / avg_cost * 100
    net_pct = net_pnl_pct_short(avg_cost, price, symbol, hold_sec=hold_sec, leverage=leverage)
    roe_pct = pnl_pct * leverage
    min_net = min_net_profit_pct(symbol, hold_sec, leverage)
    tp_pct, sl_pct = tp_sl_for_symbol(symbol)
    tp_pct = effective_take_profit_pct(symbol, tp_pct, hold_sec, leverage)

    if (
        settings.quant_scalp_breakeven_trigger_pct > 0
        and net_pct >= min_net
        and pnl_pct >= settings.quant_scalp_breakeven_trigger_pct
        and (state.stop_floor is None or state.stop_floor > avg_cost)
    ):
        lock_gross = gross_for_net_profit(symbol, min_net, hold_sec, leverage)
        state.stop_floor = avg_cost * (1 - lock_gross / 100)

    if pnl_pct >= tp_pct and net_pct >= min_net:
        return ExitDecision(
            f"Short take profit net +{net_pct:.2f}% (gross +{pnl_pct:.2f}%)",
            state,
        )

    if settings.quant_leverage_enabled and leverage > 1.0:
        if roe_pct >= settings.quant_scalp_tp_roe_pct and net_pct >= min_net:
            return ExitDecision(
                f"Short ROE take profit net +{net_pct:.2f}% (ROE {roe_pct:+.2f}%)",
                state,
            )
        if roe_pct <= -settings.quant_scalp_sl_roe_pct:
            return ExitDecision(
                f"Short ROE stop {roe_pct:.2f}% ({pnl_pct:+.2f}% @ {leverage:.0f}x)",
                state,
            )

    if state.stop_floor is not None and price >= state.stop_floor:
        if net_pct >= min_net:
            return ExitDecision(
                f"Short profit lock net +{net_pct:.2f}% @ ${price:.2f}",
                state,
            )

    if pnl_pct <= -sl_pct:
        return ExitDecision(
            f"Short stop loss {pnl_pct:.2f}% (ROE {roe_pct:+.2f}%)",
            state,
        )

    if trough < avg_cost and settings.quant_scalp_trail_stop_pct > 0:
        trail_rise = (price - trough) / trough * 100
        if trail_rise >= settings.quant_scalp_trail_stop_pct and net_pct >= min_net:
            return ExitDecision(
                f"Short trailing net +{net_pct:.2f}% (+{trail_rise:.2f}% from trough)",
                state,
            )

    max_hold = max_hold_for_symbol(symbol)
    if hold_sec >= max_hold:
        return ExitDecision(
            f"Short max hold {int(hold_sec)}s (net {net_pct:+.2f}%)",
            state,
        )

    return ExitDecision(None, state)
