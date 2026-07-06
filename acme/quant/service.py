"""Quant research cycle — ingest, believe, trade."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.config import settings
from acme.db.models import Episode, QuantCycleState
from acme.db.session import SessionLocal
from acme.engines.belief import BeliefEngine
from acme.graph.neo4j_client import neo4j_client
from acme.llm.factory import get_llm_client
from acme.orchestrator import ACMEOrchestrator
from acme.quant.market import (
    fetch_bars,
    fetch_intraday_bars,
    fetch_quotes,
    format_bar_summary,
    format_quote_experience,
    quote_cache,
)
from acme.quant.news import fetch_news, format_news_experience
from acme.quant.market_hours import cycle_interval_sec, quant_trading_session
from acme.quant.paper_broker import PaperBroker
from acme.quant.scalp import (
    adaptive_momentum_threshold,
    format_scalp_experience,
    is_actionable_belief,
    merge_mark_prices,
    quotes_from_intraday,
    rank_scalp_signals,
    scan_scalp_signals,
)
from acme.quant.fees import leverage_for_symbol, max_buy_notional
from acme.quant.symbols import (
    all_symbols,
    belief_matches_symbol,
    crypto_symbols,
    equity_symbols,
    is_crypto,
    split_universe,
)
from acme.quant.schemas import BeliefOut, CycleResultOut, QuantStateOut, QuoteOut, SignalOut, SnapshotPoint
from acme.quant.trace import append_cycle_step, build_trace
from acme.schemas import CognitiveProfile, ExperienceCreate, QueryRequest, SourceType

logger = logging.getLogger("acme.quant.service")


def _belief_out(b) -> BeliefOut:
    status = b.status.value if hasattr(b.status, "value") else str(b.status)
    return BeliefOut(
        graph_id=b.entity_or_relation_id,
        label=b.label,
        status=status,
        crs=b.crs,
        confidence=b.confidence,
        supporting_evidence=b.supporting_evidence,
        contradicting_evidence=b.contradicting_evidence,
        prediction_successes=b.prediction_successes,
        prediction_failures=b.prediction_failures,
    )


def _symbols() -> list[str]:
    return all_symbols()


TRADE_DECISION_PROMPT = """You are a quantitative research agent with access to ACME memory (beliefs, episodes, graph).

Given the portfolio state and memory context, decide if there is ONE actionable paper trade.

Return ONLY valid JSON:
{
  "action": "trade" | "hold",
  "symbol": "TICKER",
  "side": "buy" | "sell",
  "reasoning": "1-2 sentences citing beliefs/evidence",
  "belief_graph_id": "relation:xxx or null",
  "confidence": 0.0-1.0
}

Rules:
- Only trade symbols in the watchlist
- Prefer beliefs with high CRS
- Max one trade per cycle
- "hold" if no clear edge
- Demo account only — be conservative"""


class QuantService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self.tenant_id = settings.quant_tenant_id
        self.broker = PaperBroker(self.tenant_id)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        quote_cache.ttl_sec = float(settings.quant_quote_cache_sec)
        asyncio.create_task(quote_cache.warm(_symbols()))
        self._task = asyncio.create_task(self._loop())
        logger.info("Quant demo started (tenant=%s, interval=%ds)", self.tenant_id, settings.quant_cycle_interval_sec)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Quant demo stopped")

    async def _loop(self) -> None:
        await asyncio.sleep(settings.quant_cycle_startup_delay_sec)
        while self._running:
            try:
                await self.run_cycle()
            except Exception:
                logger.exception("Quant cycle failed")
            session = quant_trading_session(crypto_enabled=settings.quant_crypto_enabled)
            interval = cycle_interval_sec(
                session,
                settings.quant_cycle_interval_sec,
                settings.quant_cycle_interval_closed_sec,
            )
            await asyncio.sleep(interval)

    async def _cycle_state(self, session: AsyncSession) -> QuantCycleState:
        result = await session.execute(
            select(QuantCycleState).where(QuantCycleState.tenant_id == self.tenant_id)
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = QuantCycleState(tenant_id=self.tenant_id)
            session.add(state)
            await session.flush()
        return state

    async def run_cycle(self) -> CycleResultOut:
        if settings.quant_scalp_mode:
            return await self._run_scalp_cycle()
        return await self._run_research_cycle()

    async def _run_scalp_cycle(self) -> CycleResultOut:
        """Fast 5m scalp cycle — rule signals, TP/SL exits, light belief ingest."""
        ingested = 0
        trades_executed = 0
        symbols = _symbols()
        market = quant_trading_session(crypto_enabled=settings.quant_crypto_enabled)
        equity_trade = market["equities_open"] or not settings.quant_trade_only_market_hours
        crypto_trade = settings.quant_crypto_enabled
        eq_syms, cr_syms = split_universe(symbols)

        async with SessionLocal() as session:
            orch = ACMEOrchestrator(session, neo4j_client, get_llm_client(), tenant_id=self.tenant_id)
            cycle_state = await self._cycle_state(session)

            quotes_raw = await fetch_quotes(symbols, force=True)
            intraday = await fetch_intraday_bars(symbols)
            daily_map = {q["symbol"]: q["price"] for q in quotes_raw}
            quote_map = merge_mark_prices(symbols, intraday, daily_map)

            await self.broker.accrue_carry_costs(session, quote_map)

            # 1. Risk exits first (TP / SL / trail / max hold)
            exit_trades = await self.broker.process_scalp_exits(session, quote_map)
            trades_executed += len(exit_trades)

            # 2. Scalp signals — equities in US session, crypto 24/7
            ranked: list[dict] = []
            if equity_trade and eq_syms:
                eq_intraday = {s: intraday[s] for s in eq_syms if s in intraday}
                eq_thresh = adaptive_momentum_threshold(
                    eq_intraday,
                    settings.quant_scalp_momentum_threshold_pct,
                    floor=settings.quant_scalp_momentum_floor_pct,
                )
                ranked.extend(
                    scan_scalp_signals(
                        eq_intraday,
                        momentum_threshold_pct=eq_thresh,
                        require_fresh=True,
                    )
                )
            if crypto_trade and cr_syms:
                cr_intraday = {s: intraday[s] for s in cr_syms if s in intraday}
                cr_thresh = adaptive_momentum_threshold(
                    cr_intraday,
                    settings.quant_scalp_momentum_threshold_pct,
                    floor=settings.quant_crypto_momentum_floor_pct,
                )
                ranked.extend(
                    scan_scalp_signals(
                        cr_intraday,
                        momentum_threshold_pct=cr_thresh,
                        require_fresh=True,
                    )
                )
            ranked = rank_scalp_signals(ranked)

            def _can_trade_symbol(sym: str) -> bool:
                if is_crypto(sym):
                    return crypto_trade
                return equity_trade

            held = {p.symbol for p in (await self.broker.get_positions(session))}
            sells = [s for s in ranked if s["side"] == "sell" and s["symbol"] in held]
            buys = [s for s in ranked if s["side"] == "buy" and s["symbol"] not in held]

            belief_engine = BeliefEngine(session, tenant_id=self.tenant_id)
            belief_rows = await belief_engine.list_beliefs(min_confidence=0.0)
            actionable = [b for b in belief_rows if is_actionable_belief(b.label)]
            beliefs_out = [_belief_out(b) for b in (actionable or belief_rows)[:20]]

            def _belief_for(sym: str) -> tuple[str | None, str | None, float | None]:
                for b in beliefs_out:
                    if belief_matches_symbol(b.label, sym) and is_actionable_belief(b.label):
                        return b.graph_id, b.label, b.crs
                for b in beliefs_out:
                    if belief_matches_symbol(b.label, sym):
                        return b.graph_id, b.label, b.crs
                return None, None, None

            def _position_pct(sym: str) -> float:
                if is_crypto(sym):
                    return settings.quant_crypto_position_pct
                return settings.quant_scalp_position_pct

            portfolio = await self.broker.portfolio(session, quote_map)
            max_trades = settings.quant_max_trades_per_cycle
            trade_budget = max_trades - trades_executed

            if equity_trade or crypto_trade:
                for sig in sells[:trade_budget]:
                    if not _can_trade_symbol(sig["symbol"]):
                        continue
                    price = quote_map.get(sig["symbol"], sig["price"])
                    pos = next((p for p in portfolio.positions if p.symbol == sig["symbol"]), None)
                    if not pos:
                        continue
                    bid, blabel, bcrs = _belief_for(sig["symbol"])
                    trade = await self.broker.execute_market_order(
                        session,
                        symbol=sig["symbol"],
                        side="sell",
                        quantity=pos.quantity,
                        price=price,
                        belief_graph_id=bid,
                        belief_label=blabel or "scalp_momentum",
                        reasoning=sig["reasoning"],
                        crs_at_trade=bcrs or sig.get("confidence"),
                    )
                    if trade:
                        trades_executed += 1
                        trade_budget -= 1

                portfolio = await self.broker.portfolio(session, quote_map)
                for sig in buys[:trade_budget]:
                    if not _can_trade_symbol(sig["symbol"]):
                        continue
                    price = quote_map.get(sig["symbol"], sig["price"])
                    if price <= 0:
                        continue
                    lev = leverage_for_symbol(sig["symbol"])
                    pct = _position_pct(sig["symbol"])
                    max_notional = min(
                        max_buy_notional(portfolio.buying_power * pct, sig["symbol"], lev),
                        portfolio.nav * pct * lev,
                    )
                    qty = max_notional / price
                    if qty < 0.0001:
                        continue
                    bid, blabel, bcrs = _belief_for(sig["symbol"])
                    trade = await self.broker.execute_market_order(
                        session,
                        symbol=sig["symbol"],
                        side="buy",
                        quantity=qty,
                        price=price,
                        belief_graph_id=bid,
                        belief_label=blabel or "scalp_momentum",
                        reasoning=sig["reasoning"],
                        crs_at_trade=bcrs or sig.get("confidence"),
                    )
                    if trade:
                        trades_executed += 1

            # 3. Light ingest — top movers (crypto 24/7, equities in session)
            ingest_active = (equity_trade and eq_syms) or (crypto_trade and cr_syms)
            if (
                ingest_active
                and settings.quant_light_ingest
                and cycle_state.cycle_count % settings.quant_ingest_every_n_cycles == 0
            ):
                mover_pool: list[tuple[str, list]] = []
                if equity_trade:
                    mover_pool.extend(
                        (sym, bars) for sym, bars in intraday.items() if sym in eq_syms and bars
                    )
                if crypto_trade:
                    mover_pool.extend(
                        (sym, bars) for sym, bars in intraday.items() if sym in cr_syms and bars
                    )
                movers = sorted(
                    mover_pool,
                    key=lambda x: abs(
                        (x[1][-1]["close"] - x[1][-2]["close"]) / x[1][-2]["close"] * 100
                        if len(x[1]) > 1 and x[1][-2]["close"]
                        else 0
                    ),
                    reverse=True,
                )[:3]
                for sym, bars in movers:
                    exp = ExperienceCreate(
                        content=format_scalp_experience(sym, bars, settings.quant_bar_interval),
                        action="scalp_bar",
                        tags=["scalp", sym, settings.quant_bar_interval, "momentum"],
                        source_type=SourceType.API,
                        source_id=f"yahoo-{settings.quant_bar_interval}:{sym}",
                        source_credibility=0.95,
                        cognitive_profile=CognitiveProfile.STRATEGIC,
                        context={"symbol": sym, "interval": settings.quant_bar_interval},
                        tenant_id=self.tenant_id,
                    )
                    await orch.ingest_experience(exp)
                    ingested += 1
            else:
                for q in quotes_raw:
                    await orch.ingest_experience(
                        ExperienceCreate(
                            content=format_quote_experience(q),
                            action="market_tick",
                            tags=["market", q["symbol"], "scalp"],
                            source_type=SourceType.API,
                            source_id=f"yahoo-quote:{q['symbol']}",
                            source_credibility=0.95,
                            cognitive_profile=CognitiveProfile.STRATEGIC,
                            tenant_id=self.tenant_id,
                        )
                    )
                    ingested += 1

            # News only for equities during US session
            if equity_trade and cycle_state.cycle_count % settings.quant_news_every_n_cycles == 0:
                for headline in await fetch_news(eq_syms[:4], settings.quant_news_per_symbol):
                    await orch.ingest_experience(
                        ExperienceCreate(
                            content=format_news_experience(headline),
                            action="news_headline",
                            tags=["news", headline["symbol"], "scalp"],
                            source_type=SourceType.WEB,
                            source_id=headline.get("source_id"),
                            source_credibility=0.7,
                            cognitive_profile=CognitiveProfile.STRATEGIC,
                            tenant_id=self.tenant_id,
                        )
                    )
                    ingested += 1

            beliefs_out = [
                _belief_out(b)
                for b in (actionable or belief_rows)[:20]
            ]
            portfolio = await self.broker.portfolio(session, quote_map)
            await self.broker.record_snapshot(
                session,
                nav=portfolio.nav,
                total_pnl_pct=portfolio.total_pnl_pct,
                positions_json=[p.model_dump() for p in portfolio.positions],
            )

            trades = await self.broker.list_trades(session, limit=10)
            ep_result = await session.execute(
                select(Episode)
                .where(Episode.tenant_id == self.tenant_id)
                .order_by(Episode.created_at.desc())
                .limit(12)
            )
            episodes = [
                {"text": e.content[:120], "time": e.created_at.strftime("%H:%M") if e.created_at else ""}
                for e in ep_result.scalars().all()
            ]
            trace = build_trace(
                episodes=episodes,
                beliefs=beliefs_out,
                trades=trades,
                existing_nodes=cycle_state.trace_nodes,
                existing_edges=cycle_state.trace_edges,
                existing_steps=cycle_state.trace_steps,
            )
            now_str = datetime.now(timezone.utc).strftime("%H:%M")
            max_crs = max((b.crs for b in beliefs_out), default=0.4)
            thresh_note = ""
            if crypto_trade and cr_syms:
                thresh_note = "crypto+eq" if equity_trade else "crypto 24/7"
            elif equity_trade:
                thresh_note = "equities"
            status_note = market["label"] if not thresh_note else f"{thresh_note} · {market['label']}"
            new_steps = append_cycle_step(
                trace.steps,
                title=f"Cycle {cycle_state.cycle_count + 1}",
                phase="cycle",
                crs=max_crs,
                summary=f"{trades_executed} fills · {len(ranked)} signals · {status_note}",
                episode_text=(
                    f"{settings.quant_bar_interval} scalp: {trades_executed} trade(s), "
                    f"{len(ranked)} signals"
                ),
                time_str=now_str,
                active_nodes=[n["id"] for n in trace.nodes if n["column"] in ("market", "belief", "trade")][:8],
                inspector={
                    "type": "Cycle",
                    "title": f"Scalp cycle {cycle_state.cycle_count + 1}",
                    "desc": status_note,
                    "stats": {
                        "trades": str(trades_executed),
                        "signals": str(len(ranked)),
                        "beliefs": str(len(beliefs_out)),
                        "CRS": f"{max_crs:.2f}",
                    },
                },
            )
            cycle_state.cycle_count += 1
            cycle_state.last_cycle_at = datetime.now(timezone.utc)
            cycle_state.last_ingested = ingested
            cycle_state.trace_nodes = trace.nodes
            cycle_state.trace_edges = trace.edges
            cycle_state.trace_steps = new_steps
            await session.commit()

            return CycleResultOut(
                ok=True,
                ingested=ingested,
                beliefs_count=len(beliefs_out),
                trades_executed=trades_executed,
                message=(
                    f"Scalp cycle {cycle_state.cycle_count}: {trades_executed} trades, "
                    f"{len(ranked)} signals · {market['label']}"
                ),
            )

    async def _run_research_cycle(self) -> CycleResultOut:
        ingested = 0
        trades_executed = 0
        symbols = _symbols()

        async with SessionLocal() as session:
            llm = get_llm_client()
            orch = ACMEOrchestrator(session, neo4j_client, llm, tenant_id=self.tenant_id)
            cycle_state = await self._cycle_state(session)

            # 1. Fetch real market data
            quotes_raw = await fetch_quotes(symbols, force=True)
            news_raw = await fetch_news(symbols, settings.quant_news_per_symbol)

            for q in quotes_raw:
                exp = ExperienceCreate(
                    content=format_quote_experience(q),
                    action="market_tick",
                    tags=["market", q["symbol"], "equity", "quote"],
                    source_type=SourceType.API,
                    source_id=f"yahoo-quote:{q['symbol']}",
                    source_credibility=0.95,
                    cognitive_profile=CognitiveProfile.STRATEGIC,
                    context={"symbol": q["symbol"], "price": q["price"], "change_pct": q["change_pct"]},
                    tenant_id=self.tenant_id,
                )
                await orch.ingest_experience(exp)
                ingested += 1

            for headline in news_raw:
                exp = ExperienceCreate(
                    content=format_news_experience(headline),
                    action="news_headline",
                    tags=["news", headline["symbol"], "market"],
                    source_type=SourceType.WEB,
                    source_id=headline.get("source_id"),
                    source_credibility=0.7,
                    cognitive_profile=CognitiveProfile.STRATEGIC,
                    context={"symbol": headline["symbol"], "link": headline.get("link", "")},
                    tenant_id=self.tenant_id,
                )
                await orch.ingest_experience(exp)
                ingested += 1

            # Bar summaries for top movers
            for q in sorted(quotes_raw, key=lambda x: abs(x["change_pct"]), reverse=True)[:3]:
                bars = await fetch_bars(q["symbol"])
                if bars:
                    exp = ExperienceCreate(
                        content=format_bar_summary(q["symbol"], bars),
                        action="market_bars",
                        tags=["market", q["symbol"], "technical"],
                        source_type=SourceType.API,
                        source_id=f"yahoo-bars:{q['symbol']}",
                        source_credibility=0.9,
                        cognitive_profile=CognitiveProfile.STRATEGIC,
                        tenant_id=self.tenant_id,
                    )
                    await orch.ingest_experience(exp)
                    ingested += 1

            # 2. List beliefs
            belief_engine = BeliefEngine(session, tenant_id=self.tenant_id)
            belief_rows = await belief_engine.list_beliefs(min_confidence=0.0)
            beliefs_out = [_belief_out(b) for b in belief_rows[:20]]

            # 3. Research query for trade decision
            quote_map = {q["symbol"]: q["price"] for q in quotes_raw}
            portfolio = await self.broker.portfolio(session, quote_map)

            top_beliefs = [b for b in beliefs_out if b.crs >= settings.quant_min_belief_crs]
            belief_summary = "\n".join(
                f"- [{b.crs:.2f}] {b.label} ({b.status})" for b in top_beliefs[:5]
            ) or "No promoted beliefs yet."

            question = (
                f"Watchlist: {', '.join(symbols)}. "
                f"Portfolio NAV ${portfolio.nav:,.0f}, cash ${portfolio.cash:,.0f}. "
                f"Top beliefs:\n{belief_summary}\n"
                f"Any actionable paper trade? Reply with trade decision."
            )
            qr = await orch.query(QueryRequest(question=question))

            # 4. Parse LLM trade decision
            decision = self._parse_trade_decision(qr.answer, symbols)
            if decision.get("action") == "trade":
                sym = decision.get("symbol", "").upper()
                side = decision.get("side", "buy").lower()
                price = quote_map.get(sym, 0)
                if price > 0:
                    max_notional = portfolio.nav * settings.quant_max_position_pct
                    qty = max_notional / price
                    existing = next((p for p in portfolio.positions if p.symbol == sym), None)
                    if side == "sell" and existing:
                        qty = min(qty, existing.quantity)
                    elif side == "buy":
                        qty = min(qty, portfolio.cash / price)

                    belief_id = decision.get("belief_graph_id")
                    belief_label = None
                    crs_val = decision.get("confidence")
                    for b in beliefs_out:
                        if b.graph_id == belief_id:
                            belief_label = b.label
                            crs_val = b.crs
                            break

                    trade = await self.broker.execute_market_order(
                        session,
                        symbol=sym,
                        side=side,
                        quantity=qty,
                        price=price,
                        belief_graph_id=belief_id,
                        belief_label=belief_label,
                        reasoning=decision.get("reasoning", qr.reasoning[:500]),
                        crs_at_trade=crs_val,
                    )
                    if trade:
                        trades_executed += 1
                        exp = ExperienceCreate(
                            content=f"Paper {side} {qty:.2f} {sym} @ ${price:.2f} — {decision.get('reasoning', '')}",
                            action="paper_trade",
                            tags=["trade", sym, side, "paper"],
                            source_type=SourceType.SYSTEM,
                            source_credibility=1.0,
                            cognitive_profile=CognitiveProfile.STRATEGIC,
                            context={"trade_id": str(trade.id), "belief_graph_id": belief_id},
                            tenant_id=self.tenant_id,
                        )
                        await orch.ingest_experience(exp)
                        ingested += 1

            # 5. Portfolio snapshot
            quote_map = {q["symbol"]: q["price"] for q in quotes_raw}
            portfolio = await self.broker.portfolio(session, quote_map)
            await self.broker.record_snapshot(
                session,
                nav=portfolio.nav,
                total_pnl_pct=portfolio.total_pnl_pct,
                positions_json=[p.model_dump() for p in portfolio.positions],
            )

            # 6. Update trace
            ep_result = await session.execute(
                select(Episode)
                .where(Episode.tenant_id == self.tenant_id)
                .order_by(Episode.created_at.desc())
                .limit(12)
            )
            episodes = [
                {
                    "text": e.content[:120],
                    "time": e.created_at.strftime("%H:%M") if e.created_at else "",
                }
                for e in ep_result.scalars().all()
            ]
            trades = await self.broker.list_trades(session, limit=10)
            trace = build_trace(
                episodes=episodes,
                beliefs=beliefs_out,
                trades=trades,
                existing_nodes=cycle_state.trace_nodes,
                existing_edges=cycle_state.trace_edges,
                existing_steps=cycle_state.trace_steps,
            )

            now_str = datetime.now(timezone.utc).strftime("%H:%M")
            max_crs = max((b.crs for b in beliefs_out), default=0.4)
            new_steps = append_cycle_step(
                trace.steps,
                title=f"Cycle {cycle_state.cycle_count + 1}",
                crs=max_crs,
                episode_text=f"Ingested {ingested} experiences, {trades_executed} trade(s)",
                time_str=now_str,
                active_nodes=[n["id"] for n in trace.nodes[:6]],
            )

            cycle_state.cycle_count += 1
            cycle_state.last_cycle_at = datetime.now(timezone.utc)
            cycle_state.last_ingested = ingested
            cycle_state.trace_nodes = trace.nodes
            cycle_state.trace_edges = trace.edges
            cycle_state.trace_steps = new_steps

            await session.commit()

            return CycleResultOut(
                ok=True,
                ingested=ingested,
                beliefs_count=len(beliefs_out),
                trades_executed=trades_executed,
                message=f"Cycle {cycle_state.cycle_count}: {ingested} ingested, {trades_executed} trades",
            )

    def _parse_trade_decision(self, answer: str, symbols: list[str]) -> dict:
        try:
            match = re.search(r"\{[\s\S]*\}", answer)
            if match:
                data = json.loads(match.group())
                sym = str(data.get("symbol", "")).upper()
                if sym and sym not in symbols:
                    data["action"] = "hold"
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        return {"action": "hold"}

    async def get_state(self, session: AsyncSession) -> QuantStateOut:
        symbols = _symbols()
        quotes_raw = await fetch_quotes(symbols)
        daily_map = {q["symbol"]: q["price"] for q in quotes_raw}

        if settings.quant_scalp_mode:
            intraday = await fetch_intraday_bars(symbols)
            quote_map = merge_mark_prices(symbols, intraday, daily_map)
            quotes_raw = quotes_from_intraday(symbols, intraday, quotes_raw)
        else:
            quote_map = daily_map

        portfolio = await self.broker.portfolio(session, quote_map)
        trades = await self.broker.list_trades(session, limit=30)

        belief_engine = BeliefEngine(session, tenant_id=self.tenant_id)
        belief_rows = await belief_engine.list_beliefs(min_confidence=0.0)
        actionable = [b for b in belief_rows if is_actionable_belief(b.label)]
        beliefs_out = [_belief_out(b) for b in (actionable or belief_rows)[:20]]

        cycle_state = await self._cycle_state(session)
        market = quant_trading_session(crypto_enabled=settings.quant_crypto_enabled)
        effective_interval = cycle_interval_sec(
            market,
            settings.quant_cycle_interval_sec,
            settings.quant_cycle_interval_closed_sec,
        )

        ep_result = await session.execute(
            select(Episode)
            .where(Episode.tenant_id == self.tenant_id)
            .order_by(Episode.created_at.desc())
            .limit(12)
        )
        episodes = [
            {"text": e.content[:120], "time": e.created_at.strftime("%H:%M") if e.created_at else ""}
            for e in ep_result.scalars().all()
        ]

        trace = build_trace(
            episodes=episodes,
            beliefs=beliefs_out,
            trades=trades,
            existing_nodes=cycle_state.trace_nodes,
            existing_edges=cycle_state.trace_edges,
            existing_steps=cycle_state.trace_steps,
        )

        from acme.db.models import PortfolioSnapshot

        snap_result = await session.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.tenant_id == self.tenant_id)
            .order_by(PortfolioSnapshot.created_at.asc())
            .limit(200)
        )
        equity_curve = [
            SnapshotPoint(
                timestamp=s.created_at,
                nav=s.nav,
                total_pnl_pct=s.total_pnl_pct,
            )
            for s in snap_result.scalars().all()
        ]

        signals = [
            SignalOut(
                id=t.id,
                symbol=t.symbol,
                side=t.side,
                quantity=t.quantity,
                price=t.price,
                timestamp=t.created_at,
                belief_graph_id=t.belief_graph_id,
                belief_label=t.belief_label,
                crs=t.crs_at_trade,
                reasoning=t.reasoning or "",
            )
            for t in trades[:20]
        ]

        return QuantStateOut(
            portfolio=portfolio,
            quotes=[
                QuoteOut(
                    symbol=q["symbol"],
                    price=q["price"],
                    change_pct=q["change_pct"],
                    volume=q.get("volume"),
                    market_cap=q.get("market_cap"),
                    timestamp=q["timestamp"],
                )
                for q in quotes_raw
            ],
            beliefs=beliefs_out,
            trades=trades,
            signals=signals,
            trace=trace,
            equity_curve=equity_curve,
            cycle_count=cycle_state.cycle_count,
            last_cycle_at=cycle_state.last_cycle_at,
            watchlist=symbols,
            scalp_mode=settings.quant_scalp_mode,
            bar_interval=settings.quant_bar_interval,
            cycle_interval_sec=effective_interval,
            market_open=bool(market.get("open")),
            equities_open=bool(market.get("equities_open")),
            market_status=str(market.get("status", "unknown")),
            market_label=str(market.get("label", "")),
            crypto_enabled=settings.quant_crypto_enabled,
            crypto_symbols=crypto_symbols(),
        )


quant_service = QuantService()
