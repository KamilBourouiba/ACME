"""Paper trading broker — demo account with market orders."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.config import settings
from acme.db.models import PaperAccount, PaperPosition, PaperTrade, PortfolioSnapshot
from acme.quant.schemas import PortfolioOut, PositionOut, TradeOut

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
            )
            session.add(acct)
            await session.flush()
        return acct

    async def get_positions(self, session: AsyncSession) -> list[PaperPosition]:
        acct = await self.ensure_account(session)
        result = await session.execute(
            select(PaperPosition).where(PaperPosition.account_id == acct.id)
        )
        return list(result.scalars().all())

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
        notional = round(quantity * price, 2)

        if side == "buy" and acct.cash < notional:
            quantity = acct.cash / price
            notional = round(quantity * price, 2)
            if quantity < 0.001:
                logger.info("Insufficient cash for %s buy", symbol)
                return None

        pos_result = await session.execute(
            select(PaperPosition).where(
                PaperPosition.account_id == acct.id,
                PaperPosition.symbol == symbol,
            )
        )
        pos = pos_result.scalar_one_or_none()

        if side == "sell":
            if pos is None or pos.quantity < quantity:
                if pos is None:
                    return None
                quantity = pos.quantity
                notional = round(quantity * price, 2)

        trade = PaperTrade(
            account_id=acct.id,
            tenant_id=self.tenant_id,
            symbol=symbol,
            side=side,
            quantity=round(quantity, 6),
            price=round(price, 4),
            notional=notional,
            belief_graph_id=belief_graph_id,
            belief_label=belief_label,
            reasoning=reasoning[:2000],
            crs_at_trade=crs_at_trade,
        )
        session.add(trade)

        if side == "buy":
            acct.cash = round(acct.cash - notional, 2)
            if pos is None:
                pos = PaperPosition(
                    account_id=acct.id,
                    tenant_id=self.tenant_id,
                    symbol=symbol,
                    quantity=quantity,
                    avg_cost=price,
                )
                session.add(pos)
            else:
                total_cost = pos.avg_cost * pos.quantity + notional
                pos.quantity = round(pos.quantity + quantity, 6)
                pos.avg_cost = round(total_cost / pos.quantity, 4)
        else:
            acct.cash = round(acct.cash + notional, 2)
            pos.quantity = round(pos.quantity - quantity, 6)
            if pos.quantity < 0.0001:
                await session.delete(pos)

        await session.flush()
        return trade

    async def portfolio(
        self,
        session: AsyncSession,
        quotes: dict[str, float],
    ) -> PortfolioOut:
        acct = await self.ensure_account(session)
        positions = await self.get_positions(session)

        pos_out: list[PositionOut] = []
        invested = 0.0
        unrealized_total = 0.0

        for p in positions:
            mkt = quotes.get(p.symbol, p.avg_cost)
            mkt_val = p.quantity * mkt
            cost_basis = p.quantity * p.avg_cost
            upnl = mkt_val - cost_basis
            upnl_pct = (upnl / cost_basis * 100) if cost_basis else 0.0
            invested += mkt_val
            unrealized_total += upnl
            pos_out.append(
                PositionOut(
                    symbol=p.symbol,
                    quantity=p.quantity,
                    avg_cost=p.avg_cost,
                    market_price=mkt,
                    market_value=round(mkt_val, 2),
                    unrealized_pnl=round(upnl, 2),
                    unrealized_pnl_pct=round(upnl_pct, 3),
                    weight_pct=0.0,
                )
            )

        nav = round(acct.cash + invested, 2)
        for po in pos_out:
            po.weight_pct = round(po.market_value / nav * 100, 2) if nav else 0.0

        total_pnl = nav - acct.starting_cash
        total_pnl_pct = (total_pnl / acct.starting_cash * 100) if acct.starting_cash else 0.0

        snap_result = await session.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.tenant_id == self.tenant_id)
            .order_by(PortfolioSnapshot.created_at.desc())
            .limit(2)
        )
        snaps = list(snap_result.scalars().all())
        daily_pnl = 0.0
        daily_pnl_pct = 0.0
        if len(snaps) >= 2:
            daily_pnl = nav - snaps[1].nav
            daily_pnl_pct = (daily_pnl / snaps[1].nav * 100) if snaps[1].nav else 0.0

        return PortfolioOut(
            tenant_id=self.tenant_id,
            cash=round(acct.cash, 2),
            starting_cash=acct.starting_cash,
            nav=nav,
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 3),
            daily_pnl=round(daily_pnl, 2),
            daily_pnl_pct=round(daily_pnl_pct, 3),
            positions=sorted(pos_out, key=lambda x: -x.market_value),
            updated_at=datetime.now(timezone.utc),
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
        await session.flush()
