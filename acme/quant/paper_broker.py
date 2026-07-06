"""Paper trading broker — margin, leverage, and realistic fees."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.config import settings
from acme.db.models import PaperAccount, PaperPosition, PaperTrade, PortfolioSnapshot
from acme.quant.fees import (
    borrowed_from_cost,
    carry_cost,
    leverage_for_symbol,
    margin_required,
    max_buy_notional,
    trade_commission,
)
from acme.quant.schemas import PortfolioOut, PositionOut, TradeOut
from acme.quant.risk import evaluate_exit

logger = logging.getLogger("acme.quant.broker")


class PaperBroker:
    def __init__(self, tenant_id: str | None = None) -> None:
        self.tenant_id = tenant_id or settings.quant_tenant_id

    async def ensure_account(self, session: AsyncSession) -> PaperAccount:
        result = await session.execute(
            select(PaperAccount).where(PaperAccount.tenant_id == self.tenant_id)
        )
        acct = result.scalar_one_or_none()
        if acct is None:
            acct = PaperAccount(
                tenant_id=self.tenant_id,
                cash=settings.quant_starting_cash,
                starting_cash=settings.quant_starting_cash,
                fees_paid=0.0,
                funding_paid=0.0,
                last_carry_at=datetime.now(timezone.utc),
            )
            session.add(acct)
            await session.flush()
        if getattr(acct, "last_carry_at", None) is None:
            acct.last_carry_at = datetime.now(timezone.utc)
        return acct

    async def get_positions(self, session: AsyncSession) -> list[PaperPosition]:
        acct = await self.ensure_account(session)
        result = await session.execute(
            select(PaperPosition).where(PaperPosition.account_id == acct.id)
        )
        return list(result.scalars().all())

    def _position_leverage(self, pos: PaperPosition) -> float:
        return max(getattr(pos, "leverage", None) or 1.0, 1.0)

    def _position_margin(self, pos: PaperPosition) -> float:
        margin = getattr(pos, "margin_used", None)
        if margin is not None and margin > 0:
            return margin
        cost = pos.quantity * pos.avg_cost
        return margin_required(cost, self._position_leverage(pos))

    def _position_borrowed(self, pos: PaperPosition) -> float:
        borrowed = getattr(pos, "borrowed", None)
        if borrowed is not None and borrowed > 0:
            return borrowed
        return borrowed_from_cost(pos.quantity * pos.avg_cost, self._position_leverage(pos))

    async def accrue_carry_costs(
        self,
        session: AsyncSession,
        quotes: dict[str, float],
    ) -> float:
        """Deduct margin interest / crypto funding from cash."""
        acct = await self.ensure_account(session)
        now = datetime.now(timezone.utc)
        last = acct.last_carry_at or now
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        hours = (now - last).total_seconds() / 3600.0
        if hours < 1 / 60:
            return 0.0

        total = 0.0
        for pos in await self.get_positions(session):
            mkt = quotes.get(pos.symbol, pos.avg_cost)
            notional = abs(pos.quantity) * mkt
            borrowed = self._position_borrowed(pos)
            cost = carry_cost(
                symbol=pos.symbol,
                borrowed=borrowed,
                notional=notional,
                hours=hours,
            )
            total += cost

        if total > 0:
            acct.cash = round(acct.cash - total, 4)
            acct.funding_paid = round((acct.funding_paid or 0) + total, 4)
        acct.last_carry_at = now
        await session.flush()
        return round(total, 4)

    async def _open_short(
        self,
        session: AsyncSession,
        *,
        acct: PaperAccount,
        positions: list[PaperPosition],
        symbol: str,
        quantity: float,
        price: float,
        leverage: float,
        quotes: dict[str, float],
        belief_graph_id: str | None,
        belief_label: str | None,
        reasoning: str,
        crs_at_trade: float | None,
    ) -> PaperTrade | None:
        notional = round(quantity * price, 2)
        fee = trade_commission(symbol, notional)
        margin = margin_required(notional, leverage)
        if margin + fee > acct.cash + 0.01:
            affordable = max_buy_notional(acct.cash, symbol, leverage)
            quantity = min(quantity, affordable / price if price else 0)
            notional = round(quantity * price, 2)
            fee = trade_commission(symbol, notional)
            margin = margin_required(notional, leverage)
        portfolio = await self.portfolio(session, quotes)
        cap = self._exposure_cap_notional(portfolio.nav, positions, quotes)
        if notional > cap:
            quantity = min(quantity, cap / price if price else 0)
            notional = round(quantity * price, 2)
            fee = trade_commission(symbol, notional)
            margin = margin_required(notional, leverage)
        if margin + fee > acct.cash or quantity < 0.0001:
            logger.info("Insufficient margin for %s short", symbol)
            return None

        trade = PaperTrade(
            account_id=acct.id,
            tenant_id=self.tenant_id,
            symbol=symbol,
            side="sell",
            quantity=round(quantity, 6),
            price=round(price, 4),
            notional=notional,
            fee=fee,
            leverage=leverage,
            belief_graph_id=belief_graph_id,
            belief_label=belief_label,
            reasoning=reasoning[:2000],
            crs_at_trade=crs_at_trade,
        )
        session.add(trade)
        acct.fees_paid = round((acct.fees_paid or 0) + fee, 4)
        acct.cash = round(acct.cash - margin - fee, 4)
        borrowed = borrowed_from_cost(notional, leverage)
        pos = PaperPosition(
            account_id=acct.id,
            tenant_id=self.tenant_id,
            symbol=symbol,
            quantity=-round(quantity, 6),
            avg_cost=price,
            leverage=leverage,
            margin_used=margin,
            borrowed=borrowed,
            opened_at=datetime.now(timezone.utc),
            peak_price=price,
            stop_floor=None,
        )
        session.add(pos)
        await session.flush()
        return trade

    async def _cover_short(
        self,
        session: AsyncSession,
        *,
        acct: PaperAccount,
        pos: PaperPosition,
        symbol: str,
        quantity: float,
        price: float,
        leverage: float,
        belief_graph_id: str | None,
        belief_label: str | None,
        reasoning: str,
        crs_at_trade: float | None,
    ) -> PaperTrade | None:
        short_qty = abs(pos.quantity)
        quantity = min(quantity, short_qty)
        if quantity < 0.0001:
            return None
        notional = round(quantity * price, 2)
        fee = trade_commission(symbol, notional)
        frac = quantity / short_qty if short_qty else 1.0
        margin_release = round(self._position_margin(pos) * frac, 4)
        borrowed_release = round(self._position_borrowed(pos) * frac, 4)
        realized = (pos.avg_cost - price) * quantity - fee

        trade = PaperTrade(
            account_id=acct.id,
            tenant_id=self.tenant_id,
            symbol=symbol,
            side="buy",
            quantity=round(quantity, 6),
            price=round(price, 4),
            notional=notional,
            fee=fee,
            leverage=leverage,
            belief_graph_id=belief_graph_id,
            belief_label=belief_label,
            reasoning=reasoning[:2000],
            crs_at_trade=crs_at_trade,
        )
        session.add(trade)
        acct.fees_paid = round((acct.fees_paid or 0) + fee, 4)
        acct.cash = round(acct.cash + margin_release + realized, 4)
        pos.quantity = round(pos.quantity + quantity, 6)
        pos.margin_used = round(max(0.0, (pos.margin_used or 0) - margin_release), 4)
        pos.borrowed = round(max(0.0, (pos.borrowed or 0) - borrowed_release), 4)
        if pos.quantity > -0.0001:
            await session.delete(pos)
        await session.flush()
        return trade

    def _exposure_cap_notional(
        self,
        nav: float,
        positions: list[PaperPosition],
        quotes: dict[str, float],
        additional: float = 0.0,
    ) -> float:
        current = sum(
            abs(p.quantity * quotes.get(p.symbol, p.avg_cost)) for p in positions
        )
        cap = nav * max(settings.quant_max_leverage, 1.0)
        return max(0.0, cap - current - additional)

    async def execute_market_order(
        self,
        session: AsyncSession,
        *,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        belief_graph_id: str | None = None,
        belief_label: str | None = None,
        reasoning: str = "",
        crs_at_trade: float | None = None,
    ) -> PaperTrade | None:
        symbol = symbol.upper().strip()
        side = side.lower().strip()
        if side not in ("buy", "sell") or quantity <= 0 or price <= 0:
            return None

        acct = await self.ensure_account(session)
        leverage = leverage_for_symbol(symbol)
        positions = await self.get_positions(session)
        quotes = {symbol: price}

        pos_result = await session.execute(
            select(PaperPosition).where(
                PaperPosition.account_id == acct.id,
                PaperPosition.symbol == symbol,
            )
        )
        pos = pos_result.scalar_one_or_none()

        if side == "buy":
            if pos is not None and pos.quantity < 0:
                return await self._cover_short(
                    session,
                    acct=acct,
                    pos=pos,
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    leverage=leverage,
                    belief_graph_id=belief_graph_id,
                    belief_label=belief_label,
                    reasoning=reasoning,
                    crs_at_trade=crs_at_trade,
                )
            notional = round(quantity * price, 2)
            fee = trade_commission(symbol, notional)
            margin = margin_required(notional, leverage)
            if margin + fee > acct.cash + 0.01:
                affordable = max_buy_notional(acct.cash, symbol, leverage)
                quantity = min(quantity, affordable / price if price else 0)
                notional = round(quantity * price, 2)
                fee = trade_commission(symbol, notional)
                margin = margin_required(notional, leverage)
            portfolio = await self.portfolio(session, quotes)
            cap = self._exposure_cap_notional(portfolio.nav, positions, quotes)
            if notional > cap:
                quantity = min(quantity, cap / price if price else 0)
                notional = round(quantity * price, 2)
                fee = trade_commission(symbol, notional)
                margin = margin_required(notional, leverage)
            if margin + fee > acct.cash or quantity < 0.0001:
                logger.info("Insufficient margin for %s buy", symbol)
                return None
        else:
            notional = round(quantity * price, 2)
            fee = trade_commission(symbol, notional)

        if side == "sell":
            if pos is None:
                return await self._open_short(
                    session,
                    acct=acct,
                    positions=positions,
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    leverage=leverage,
                    quotes=quotes,
                    belief_graph_id=belief_graph_id,
                    belief_label=belief_label,
                    reasoning=reasoning,
                    crs_at_trade=crs_at_trade,
                )
            if pos.quantity < 0:
                logger.info("Already short %s — skip add", symbol)
                return None
            if pos.quantity < quantity:
                quantity = pos.quantity
                notional = round(quantity * price, 2)
                fee = trade_commission(symbol, notional)

        trade = PaperTrade(
            account_id=acct.id,
            tenant_id=self.tenant_id,
            symbol=symbol,
            side=side,
            quantity=round(quantity, 6),
            price=round(price, 4),
            notional=notional,
            fee=fee,
            leverage=leverage,
            belief_graph_id=belief_graph_id,
            belief_label=belief_label,
            reasoning=reasoning[:2000],
            crs_at_trade=crs_at_trade,
        )
        session.add(trade)
        acct.fees_paid = round((acct.fees_paid or 0) + fee, 4)

        if side == "buy":
            acct.cash = round(acct.cash - margin - fee, 4)
            borrowed = borrowed_from_cost(notional, leverage)
            if pos is None:
                pos = PaperPosition(
                    account_id=acct.id,
                    tenant_id=self.tenant_id,
                    symbol=symbol,
                    quantity=quantity,
                    avg_cost=price,
                    leverage=leverage,
                    margin_used=margin,
                    borrowed=borrowed,
                    opened_at=datetime.now(timezone.utc),
                    peak_price=price,
                    stop_floor=None,
                )
                session.add(pos)
            else:
                old_cost = pos.quantity * pos.avg_cost
                pos.quantity = round(pos.quantity + quantity, 6)
                pos.avg_cost = round((old_cost + notional) / pos.quantity, 4)
                pos.leverage = leverage
                pos.margin_used = round((pos.margin_used or 0) + margin, 4)
                pos.borrowed = round((pos.borrowed or 0) + borrowed, 4)
        else:
            if pos is None:
                return None
            frac = quantity / pos.quantity if pos.quantity else 1.0
            margin_release = round(self._position_margin(pos) * frac, 4)
            borrowed_release = round(self._position_borrowed(pos) * frac, 4)
            cost_basis = quantity * pos.avg_cost
            proceeds = notional
            realized = proceeds - cost_basis - fee
            acct.cash = round(acct.cash + margin_release + realized, 4)
            pos.quantity = round(pos.quantity - quantity, 6)
            pos.margin_used = round(max(0.0, (pos.margin_used or 0) - margin_release), 4)
            pos.borrowed = round(max(0.0, (pos.borrowed or 0) - borrowed_release), 4)
            if pos.quantity < 0.0001:
                await session.delete(pos)

        await session.flush()
        return trade

    async def process_scalp_exits(
        self,
        session: AsyncSession,
        quotes: dict[str, float],
    ) -> list[PaperTrade]:
        """Close positions on take-profit, stop-loss, or max hold time."""
        exits: list[PaperTrade] = []
        now = datetime.now(timezone.utc)
        positions = await self.get_positions(session)

        for pos in positions:
            price = quotes.get(pos.symbol, pos.avg_cost)
            if pos.avg_cost <= 0:
                continue
            lev = self._position_leverage(pos)
            opened = pos.opened_at or pos.updated_at or now
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)

            decision = evaluate_exit(
                symbol=pos.symbol,
                avg_cost=pos.avg_cost,
                price=price,
                peak_price=getattr(pos, "peak_price", None),
                stop_floor=getattr(pos, "stop_floor", None),
                leverage=lev,
                opened_at=opened,
                now=now,
                quantity=pos.quantity,
            )
            pos.peak_price = decision.state.peak_price
            pos.stop_floor = decision.state.stop_floor

            if decision.reason:
                if pos.quantity < 0:
                    trade = await self.execute_market_order(
                        session,
                        symbol=pos.symbol,
                        side="buy",
                        quantity=abs(pos.quantity),
                        price=price,
                        belief_label="scalp_exit",
                        reasoning=decision.reason,
                    )
                else:
                    trade = await self.execute_market_order(
                        session,
                        symbol=pos.symbol,
                        side="sell",
                        quantity=pos.quantity,
                        price=price,
                        belief_label="scalp_exit",
                        reasoning=decision.reason,
                    )
                if trade:
                    exits.append(trade)
        return exits

    async def portfolio(
        self,
        session: AsyncSession,
        quotes: dict[str, float],
    ) -> PortfolioOut:
        acct = await self.ensure_account(session)
        positions = await self.get_positions(session)

        pos_out: list[PositionOut] = []
        gross_exposure = 0.0
        margin_used = 0.0
        borrowed = 0.0
        unrealized_total = 0.0

        for p in positions:
            mkt = quotes.get(p.symbol, p.avg_cost)
            mkt_val = p.quantity * mkt
            cost_basis = p.quantity * p.avg_cost
            upnl = mkt_val - cost_basis
            upnl_pct = (upnl / abs(cost_basis) * 100) if cost_basis else 0.0
            lev = self._position_leverage(p)
            pmargin = self._position_margin(p)
            pborrowed = self._position_borrowed(p)
            gross_exposure += abs(mkt_val)
            margin_used += pmargin
            borrowed += pborrowed
            unrealized_total += upnl
            pos_side = "short" if p.quantity < 0 else "long"
            pos_out.append(
                PositionOut(
                    symbol=p.symbol,
                    quantity=p.quantity,
                    side=pos_side,
                    avg_cost=p.avg_cost,
                    market_price=mkt,
                    market_value=round(mkt_val, 2),
                    unrealized_pnl=round(upnl, 2),
                    unrealized_pnl_pct=round(upnl_pct, 3),
                    weight_pct=0.0,
                    leverage=lev,
                    margin_used=round(pmargin, 2),
                    borrowed=round(pborrowed, 2),
                    roe_pct=round(upnl_pct * lev, 3),
                )
            )

        nav = round(acct.cash + margin_used + unrealized_total, 2)
        buying_power = round(max(acct.cash, 0.0), 2)
        equity = nav
        effective_leverage = round(gross_exposure / equity, 2) if equity > 0 else 0.0

        for po in pos_out:
            po.weight_pct = round(abs(po.market_value) / nav * 100, 2) if nav else 0.0

        total_pnl = nav - acct.starting_cash
        total_pnl_pct = (total_pnl / acct.starting_cash * 100) if acct.starting_cash else 0.0

        snap_result = await session.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.tenant_id == self.tenant_id)
            .order_by(PortfolioSnapshot.created_at.desc())
            .limit(2)
        )
        snaps = list(snap_result.scalars().all())
        cycle_pnl = 0.0
        cycle_pnl_pct = 0.0
        if len(snaps) >= 2:
            cycle_pnl = nav - snaps[1].nav
            cycle_pnl_pct = (cycle_pnl / snaps[1].nav * 100) if snaps[1].nav else 0.0

        return PortfolioOut(
            tenant_id=self.tenant_id,
            cash=round(acct.cash, 2),
            starting_cash=acct.starting_cash,
            nav=nav,
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 3),
            cycle_pnl=round(cycle_pnl, 2),
            cycle_pnl_pct=round(cycle_pnl_pct, 3),
            positions=sorted(pos_out, key=lambda x: -x.market_value),
            updated_at=datetime.now(timezone.utc),
            buying_power=buying_power,
            margin_used=round(margin_used, 2),
            borrowed=round(borrowed, 2),
            gross_exposure=round(gross_exposure, 2),
            effective_leverage=effective_leverage,
            fees_paid=round(acct.fees_paid or 0, 2),
            funding_paid=round(acct.funding_paid or 0, 2),
            leverage_enabled=settings.quant_leverage_enabled,
        )

    async def record_snapshot(
        self,
        session: AsyncSession,
        nav: float,
        total_pnl_pct: float,
        positions_json: list[dict[str, Any]],
    ) -> PortfolioSnapshot:
        snap = PortfolioSnapshot(
            tenant_id=self.tenant_id,
            nav=nav,
            total_pnl_pct=total_pnl_pct,
            positions_json=positions_json,
        )
        session.add(snap)
        await session.flush()
        return snap

    async def list_trades(self, session: AsyncSession, limit: int = 50) -> list[TradeOut]:
        result = await session.execute(
            select(PaperTrade)
            .where(PaperTrade.tenant_id == self.tenant_id)
            .order_by(PaperTrade.created_at.desc())
            .limit(limit)
        )
        return [
            TradeOut(
                id=t.id,
                symbol=t.symbol,
                side=t.side,
                quantity=t.quantity,
                price=t.price,
                notional=t.notional,
                fee=getattr(t, "fee", 0.0) or 0.0,
                leverage=getattr(t, "leverage", 1.0) or 1.0,
                belief_graph_id=t.belief_graph_id,
                belief_label=t.belief_label,
                reasoning=t.reasoning or "",
                crs_at_trade=t.crs_at_trade,
                created_at=t.created_at,
            )
            for t in result.scalars().all()
        ]

    async def reset(self, session: AsyncSession) -> None:
        acct = await self.ensure_account(session)
        pos_result = await session.execute(
            select(PaperPosition).where(PaperPosition.account_id == acct.id)
        )
        for p in pos_result.scalars().all():
            await session.delete(p)
        trade_result = await session.execute(
            select(PaperTrade).where(PaperTrade.tenant_id == self.tenant_id)
        )
        for t in trade_result.scalars().all():
            await session.delete(t)
        snap_result = await session.execute(
            select(PortfolioSnapshot).where(PortfolioSnapshot.tenant_id == self.tenant_id)
        )
        for s in snap_result.scalars().all():
            await session.delete(s)
        acct.cash = acct.starting_cash
        acct.fees_paid = 0.0
        acct.funding_paid = 0.0
        acct.last_carry_at = datetime.now(timezone.utc)
        await session.flush()
