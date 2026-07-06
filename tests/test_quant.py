"""Tests for the quant belief-driven paper trading demo."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from acme.config import settings
from acme.db.session import get_session
from acme.main import app
from acme.quant.paper_broker import PaperBroker
from acme.quant.schemas import (
    BeliefOut,
    PortfolioOut,
    PositionOut,
    QuantStateOut,
    QuoteOut,
    SignalOut,
    TraceOut,
)
from acme.quant.service import quant_service


@pytest.fixture(autouse=True)
def _mock_lifecycle(monkeypatch):
    monkeypatch.setattr("acme.main.init_db", AsyncMock(return_value=None))
    monkeypatch.setattr("acme.main.neo4j_client.connect", AsyncMock(return_value=None))
    monkeypatch.setattr("acme.main.neo4j_client.close", AsyncMock(return_value=None))
    monkeypatch.setattr("acme.chat.cleanup.purge_legacy_demo_data", AsyncMock(return_value=[]))
    monkeypatch.setattr("acme.quant.service.quant_service.start", AsyncMock(return_value=None))
    monkeypatch.setattr("acme.quant.service.quant_service.stop", AsyncMock(return_value=None))


@pytest.fixture
def client():
    async def _fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_session] = _fake_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _sample_state() -> QuantStateOut:
    now = datetime.now(timezone.utc)
    return QuantStateOut(
        portfolio=PortfolioOut(
            tenant_id="quant-demo",
            cash=900_000.0,
            starting_cash=1_000_000.0,
            nav=1_050_000.0,
            total_pnl=50_000.0,
            total_pnl_pct=5.0,
            daily_pnl=2_000.0,
            daily_pnl_pct=0.19,
            positions=[
                PositionOut(
                    symbol="NVDA",
                    quantity=100,
                    avg_cost=850.0,
                    market_price=875.0,
                    market_value=87_500.0,
                    unrealized_pnl=2_500.0,
                    unrealized_pnl_pct=2.94,
                    weight_pct=8.33,
                )
            ],
            updated_at=now,
        ),
        quotes=[
            QuoteOut(symbol="NVDA", price=875.0, change_pct=1.2, volume=48_000_000, market_cap=None, timestamp=now),
        ],
        beliefs=[
            BeliefOut(
                graph_id="relation:test",
                label="AI capex drives NVDA outperformance",
                status="belief",
                crs=0.72,
                confidence=0.68,
                supporting_evidence=4,
                contradicting_evidence=0,
                prediction_successes=2,
                prediction_failures=0,
            )
        ],
        trades=[],
        signals=[],
        trace=TraceOut(nodes=[], edges=[], steps=[{"title": "Market ingest", "crs": 0.5, "episodes": [], "activeNodes": [], "activeEdges": []}]),
        equity_curve=[],
        cycle_count=3,
        last_cycle_at=now,
        watchlist=["AAPL", "NVDA", "SPY"],
    )


def test_quant_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr(settings, "quant_demo_enabled", False)
    r = client.get("/api/v1/quant/state")
    assert r.status_code == 503


def test_quant_ui_available(client, monkeypatch):
    monkeypatch.setattr(settings, "quant_demo_enabled", True)
    r = client.get("/api/v1/quant/")
    assert r.status_code == 200
    assert "ACME Quant" in r.text
    assert 'href="assets/style.css' in r.text
    assert 'src="assets/app.js' in r.text


def test_quant_state(client, monkeypatch):
    monkeypatch.setattr(settings, "quant_demo_enabled", True)
    monkeypatch.setattr(quant_service, "get_state", AsyncMock(return_value=_sample_state()))
    r = client.get("/api/v1/quant/state")
    assert r.status_code == 200
    data = r.json()
    assert data["portfolio"]["nav"] == 1_050_000.0
    assert data["beliefs"][0]["crs"] == 0.72
    assert "NVDA" in data["watchlist"]


def test_quant_signals(client, monkeypatch):
    monkeypatch.setattr(settings, "quant_demo_enabled", True)
    state = _sample_state()
    monkeypatch.setattr(quant_service, "get_state", AsyncMock(return_value=state))
    r = client.get("/api/v1/quant/signals")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_quant_trace(client, monkeypatch):
    monkeypatch.setattr(settings, "quant_demo_enabled", True)
    monkeypatch.setattr(quant_service, "get_state", AsyncMock(return_value=_sample_state()))
    r = client.get("/api/v1/quant/trace")
    assert r.status_code == 200
    assert "steps" in r.json()


def test_build_trace():
    from acme.quant.trace import build_trace

    trace = build_trace(
        episodes=[{"text": "NVDA +4%", "time": "10:00"}],
        beliefs=[
            BeliefOut(
                graph_id="rel:1",
                label="Momentum thesis",
                status="hypothesis",
                crs=0.6,
                confidence=0.55,
                supporting_evidence=2,
                contradicting_evidence=0,
                prediction_successes=0,
                prediction_failures=0,
            )
        ],
        trades=[],
    )
    assert len(trace.nodes) >= 1
    assert len(trace.steps) >= 1


def test_parse_trade_decision_hold():
    result = quant_service._parse_trade_decision("No clear edge today.", ["AAPL", "NVDA"])
    assert result["action"] == "hold"


def test_parse_trade_decision_json():
    answer = 'Analysis complete. {"action": "trade", "symbol": "NVDA", "side": "buy", "confidence": 0.7}'
    result = quant_service._parse_trade_decision(answer, ["AAPL", "NVDA"])
    assert result["action"] == "trade"
    assert result["symbol"] == "NVDA"
