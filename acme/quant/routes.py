"""Quant demo API routes + dashboard static."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from acme.config import settings
from acme.db.session import get_session as get_db_session
from acme.quant.schemas import (
    BeliefOut,
    CycleResultOut,
    PortfolioOut,
    QuantStateOut,
    QuoteOut,
    SignalOut,
    TraceOut,
    TradeOut,
)
from acme.quant.service import quant_service

router = APIRouter(prefix="/quant", tags=["quant"])

_STATIC = Path(__file__).resolve().parent / "static"


def _require_quant_enabled() -> None:
    if not settings.quant_demo_enabled:
        raise HTTPException(503, "Quant demo is disabled")


@router.get("/")
async def quant_dashboard() -> FileResponse:
    _require_quant_enabled()
    return FileResponse(_STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@router.get("/assets/{path:path}")
async def quant_assets(path: str) -> FileResponse:
    _require_quant_enabled()
    target = (_STATIC / path).resolve()
    if not str(target).startswith(str(_STATIC.resolve())):
        raise HTTPException(404)
    if not target.is_file():
        raise HTTPException(404)
    return FileResponse(target, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/state", response_model=QuantStateOut)
async def get_state(session: AsyncSession = Depends(get_db_session)) -> QuantStateOut:
    _require_quant_enabled()
    return await quant_service.get_state(session)


@router.get("/portfolio", response_model=PortfolioOut)
async def get_portfolio(session: AsyncSession = Depends(get_db_session)) -> PortfolioOut:
    _require_quant_enabled()
    state = await quant_service.get_state(session)
    return state.portfolio


@router.get("/quotes", response_model=list[QuoteOut])
async def get_quotes(session: AsyncSession = Depends(get_db_session)) -> list[QuoteOut]:
    _require_quant_enabled()
    state = await quant_service.get_state(session)
    return state.quotes


@router.get("/beliefs", response_model=list[BeliefOut])
async def get_beliefs(session: AsyncSession = Depends(get_db_session)) -> list[BeliefOut]:
    _require_quant_enabled()
    state = await quant_service.get_state(session)
    return state.beliefs


@router.get("/trades", response_model=list[TradeOut])
async def get_trades(session: AsyncSession = Depends(get_db_session)) -> list[TradeOut]:
    _require_quant_enabled()
    state = await quant_service.get_state(session)
    return state.trades


@router.get("/trace", response_model=TraceOut)
async def get_trace(session: AsyncSession = Depends(get_db_session)) -> TraceOut:
    _require_quant_enabled()
    state = await quant_service.get_state(session)
    return state.trace


@router.get("/signals", response_model=list[SignalOut])
async def get_signals(
    since: datetime | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> list[SignalOut]:
    _require_quant_enabled()
    state = await quant_service.get_state(session)
    signals = state.signals
    if since:
        signals = [s for s in signals if s.timestamp >= since]
    return signals


@router.post("/cycle", response_model=CycleResultOut)
async def trigger_cycle() -> CycleResultOut:
    _require_quant_enabled()
    if settings.quant_public_readonly:
        raise HTTPException(403, "Manual cycle trigger is disabled on the public dashboard")
    return await quant_service.run_cycle()


@router.post("/reset")
async def reset_demo(session: AsyncSession = Depends(get_db_session)) -> dict:
    _require_quant_enabled()
    if settings.quant_public_readonly:
        raise HTTPException(403, "Reset is disabled on the public dashboard")
    from acme.db.models import QuantCycleState
    from acme.demo.reset import cleanup_demo_tenant
    from acme.graph.neo4j_client import neo4j_client
    from acme.quant.market import quote_cache
    from sqlalchemy import delete

    await quant_service.broker.reset(session)
    stats = await cleanup_demo_tenant(session, neo4j_client, tenant_id=quant_service.tenant_id)
    await session.execute(
        delete(QuantCycleState).where(QuantCycleState.tenant_id == quant_service.tenant_id)
    )
    await session.commit()
    quote_cache.ttl_sec = float(settings.quant_quote_cache_sec)
    return {
        "ok": True,
        "message": "Fresh start — paper account, beliefs, episodes, and graph wiped",
        "cleanup": stats,
    }
