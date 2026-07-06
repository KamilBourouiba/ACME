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
    side: str = "long"
    avg_cost: float
    market_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight_pct: float
    leverage: float = 1.0
    margin_used: float = 0.0
    borrowed: float = 0.0
    roe_pct: float = 0.0


class PortfolioOut(BaseModel):
    tenant_id: str
    cash: float
    starting_cash: float
    nav: float
    total_pnl: float
    total_pnl_pct: float
    cycle_pnl: float
    cycle_pnl_pct: float
    positions: list[PositionOut]
    updated_at: datetime
    buying_power: float = 0.0
    margin_used: float = 0.0
    borrowed: float = 0.0
    gross_exposure: float = 0.0
    effective_leverage: float = 0.0
    fees_paid: float = 0.0
    funding_paid: float = 0.0
    leverage_enabled: bool = False


class TradeOut(BaseModel):
    id: UUID
    symbol: str
    side: str
    quantity: float
    price: float
    notional: float
    fee: float = 0.0
    leverage: float = 1.0
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
    market_open: bool = False
    equities_open: bool = False
    market_status: str = "unknown"
    market_label: str = ""
    crypto_enabled: bool = False
    crypto_symbols: list[str] = []


class CycleResultOut(BaseModel):
    ok: bool
    ingested: int = 0
    beliefs_count: int = 0
    trades_executed: int = 0
    message: str = ""
