"""Scalp exit rules — TP, SL, trailing stop, breakeven, max hold, ROE caps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from acme.config import settings
from acme.quant.fees import effective_take_profit_pct
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

    if is_short:
        return _evaluate_short_exit(
            symbol=symbol,
            avg_cost=avg_cost,
            price=price,
            peak_price=peak_price,
            stop_floor=stop_floor,
            leverage=lev,
            opened_at=opened_at,
            now=now,
        )

    return _evaluate_long_exit(
        symbol=symbol,
        avg_cost=avg_cost,
        price=price,
        peak_price=peak_price,
        stop_floor=stop_floor,
        leverage=lev,
        opened_at=opened_at,
        now=now,
    )


def _evaluate_long_exit(
    *,
    symbol: str,
    avg_cost: float,
    price: float,
    peak_price: float | None,
    stop_floor: float | None,
    leverage: float,
    opened_at: datetime,
    now: datetime,
) -> ExitDecision:
    peak = max(peak_price or avg_cost, price)
    state = ExitState(peak_price=peak, stop_floor=stop_floor)

    pnl_pct = (price - avg_cost) / avg_cost * 100
    roe_pct = pnl_pct * leverage
    tp_pct, sl_pct = tp_sl_for_symbol(symbol)
    tp_pct = effective_take_profit_pct(symbol, tp_pct)

    if (
        settings.quant_scalp_breakeven_trigger_pct > 0
        and pnl_pct >= settings.quant_scalp_breakeven_trigger_pct
        and (state.stop_floor is None or state.stop_floor < avg_cost)
    ):
        lock = settings.quant_profit_lock_pct
        state.stop_floor = avg_cost * (1 + lock / 100)

    if pnl_pct >= tp_pct:
        return ExitDecision(
            f"Take profit +{pnl_pct:.2f}% (ROE {roe_pct:+.2f}% @ {leverage:.0f}x)",
            state,
        )

    if settings.quant_leverage_enabled and leverage > 1.0:
        if roe_pct >= settings.quant_scalp_tp_roe_pct:
            return ExitDecision(
                f"ROE take profit +{roe_pct:.2f}% ({pnl_pct:+.2f}% @ {leverage:.0f}x)",
                state,
            )
        if roe_pct <= -settings.quant_scalp_sl_roe_pct:
            return ExitDecision(
                f"ROE stop {roe_pct:.2f}% ({pnl_pct:+.2f}% @ {leverage:.0f}x)",
                state,
            )

    if state.stop_floor is not None and price <= state.stop_floor:
        label = "profit lock" if state.stop_floor > avg_cost else "floor"
        return ExitDecision(
            f"Stop {label} @ ${price:.2f} ({pnl_pct:+.2f}%, ROE {roe_pct:+.2f}%)",
            state,
        )

    if pnl_pct <= -sl_pct:
        return ExitDecision(
            f"Stop loss {pnl_pct:.2f}% (ROE {roe_pct:+.2f}%)",
            state,
        )

    if peak > avg_cost and settings.quant_scalp_trail_stop_pct > 0:
        trail_drop = (peak - price) / peak * 100
        if trail_drop >= settings.quant_scalp_trail_stop_pct:
            return ExitDecision(
                f"Trailing stop -{trail_drop:.2f}% from peak ${peak:.2f} ({pnl_pct:+.2f}%)",
                state,
            )

    hold_sec = (now - opened_at).total_seconds()
    max_hold = max_hold_for_symbol(symbol)
    if hold_sec >= max_hold:
        return ExitDecision(
            f"Max hold {int(hold_sec)}s ({pnl_pct:+.2f}%, ROE {roe_pct:+.2f}%)",
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
    opened_at: datetime,
    now: datetime,
) -> ExitDecision:
    """Short exits — peak_price tracks the trough (best price for the short)."""
    trough = min(peak_price or avg_cost, price)
    state = ExitState(peak_price=trough, stop_floor=stop_floor)

    pnl_pct = (avg_cost - price) / avg_cost * 100
    roe_pct = pnl_pct * leverage
    tp_pct, sl_pct = tp_sl_for_symbol(symbol)
    tp_pct = effective_take_profit_pct(symbol, tp_pct)

    if (
        settings.quant_scalp_breakeven_trigger_pct > 0
        and pnl_pct >= settings.quant_scalp_breakeven_trigger_pct
        and (state.stop_floor is None or state.stop_floor > avg_cost)
    ):
        lock = settings.quant_profit_lock_pct
        state.stop_floor = avg_cost * (1 - lock / 100)

    if pnl_pct >= tp_pct:
        return ExitDecision(
            f"Short take profit +{pnl_pct:.2f}% (ROE {roe_pct:+.2f}% @ {leverage:.0f}x)",
            state,
        )

    if settings.quant_leverage_enabled and leverage > 1.0:
        if roe_pct >= settings.quant_scalp_tp_roe_pct:
            return ExitDecision(
                f"Short ROE take profit +{roe_pct:.2f}% ({pnl_pct:+.2f}% @ {leverage:.0f}x)",
                state,
            )
        if roe_pct <= -settings.quant_scalp_sl_roe_pct:
            return ExitDecision(
                f"Short ROE stop {roe_pct:.2f}% ({pnl_pct:+.2f}% @ {leverage:.0f}x)",
                state,
            )

    if state.stop_floor is not None and price >= state.stop_floor:
        label = "profit lock" if state.stop_floor < avg_cost else "ceiling"
        return ExitDecision(
            f"Short stop {label} @ ${price:.2f} ({pnl_pct:+.2f}%, ROE {roe_pct:+.2f}%)",
            state,
        )

    if pnl_pct <= -sl_pct:
        return ExitDecision(
            f"Short stop loss {pnl_pct:.2f}% (ROE {roe_pct:+.2f}%)",
            state,
        )

    if trough < avg_cost and settings.quant_scalp_trail_stop_pct > 0:
        trail_rise = (price - trough) / trough * 100
        if trail_rise >= settings.quant_scalp_trail_stop_pct:
            return ExitDecision(
                f"Short trailing stop +{trail_rise:.2f}% from trough ${trough:.2f} ({pnl_pct:+.2f}%)",
                state,
            )

    hold_sec = (now - opened_at).total_seconds()
    max_hold = max_hold_for_symbol(symbol)
    if hold_sec >= max_hold:
        return ExitDecision(
            f"Short max hold {int(hold_sec)}s ({pnl_pct:+.2f}%, ROE {roe_pct:+.2f}%)",
            state,
        )

    return ExitDecision(None, state)
