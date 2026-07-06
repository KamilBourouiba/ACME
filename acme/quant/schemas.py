"""Pydantic schemas for the quant demo."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class QuoteOut(BaseModel):
    symbol: str
    price: float
    change_pct: float
    volume: int | None = None
    market_cap: float | None = None
    timestamp: datetime


class PositionOut(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    market_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight_pct: float


class PortfolioOut(BaseModel):
    tenant_id: str
    cash: float
    starting_cash: float
    nav: float
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    positions: list[PositionOut]
    updated_at: datetime


class TradeOut(BaseModel):
    id: UUID
    symbol: str
    side: str
    quantity: float
    price: float
    notional: float
    belief_graph_id: str | None = None
    belief_label: str | None = None
    reasoning: str = ""
    crs_at_trade: float | None = None
    created_at: datetime


class BeliefOut(BaseModel):
    graph_id: str
    label: str
    status: str
    crs: float
    confidence: float
    supporting_evidence: int
    contradicting_evidence: int
    prediction_successes: int
    prediction_failures: int


class SignalOut(BaseModel):
    id: UUID
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: datetime
    belief_graph_id: str | None = None
    belief_label: str | None = None
    crs: float | None = None
    reasoning: str = ""


class TraceOut(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    steps: list[dict[str, Any]]


class SnapshotPoint(BaseModel):
    timestamp: datetime
    nav: float
    total_pnl_pct: float


class QuantStateOut(BaseModel):
    portfolio: PortfolioOut
    quotes: list[QuoteOut]
    beliefs: list[BeliefOut]
    trades: list[TradeOut]
    signals: list[SignalOut]
    trace: TraceOut
    equity_curve: list[SnapshotPoint]
    cycle_count: int
    last_cycle_at: datetime | None = None
    watchlist: list[str]
    scalp_mode: bool = False
    bar_interval: str = "5m"
    cycle_interval_sec: int = 60


class CycleResultOut(BaseModel):
    ok: bool
    ingested: int = 0
    beliefs_count: int = 0
    trades_executed: int = 0
    message: str = ""
