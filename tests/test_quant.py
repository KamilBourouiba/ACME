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
            cycle_pnl=2_000.0,
            cycle_pnl_pct=0.19,
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


def test_scalp_signal_buy():
    from acme.quant.scalp import scalp_signal

    now = datetime.now(timezone.utc).isoformat()
    bars = [
        {"close": 100.0, "volume": 1000, "date": now},
        {"close": 100.05, "volume": 1000, "date": now},
        {"close": 100.08, "volume": 1000, "date": now},
        {"close": 100.15, "volume": 5000, "date": now},
    ]
    sig = scalp_signal("NVDA", bars, momentum_threshold_pct=0.05, require_fresh=True)
    assert sig is not None
    assert sig["side"] == "buy"


def test_adaptive_momentum_threshold():
    from acme.quant.scalp import adaptive_momentum_threshold

    intraday = {
        "A": [{"close": 100, "volume": 1}, {"close": 100.02, "volume": 1}],
        "B": [{"close": 50, "volume": 1}, {"close": 50.01, "volume": 1}],
    }
    t = adaptive_momentum_threshold(intraday, base=0.06, floor=0.02)
    assert 0.02 <= t <= 0.06


def test_is_actionable_belief_filters_price_observations():
    from acme.quant.scalp import is_actionable_belief

    assert not is_actionable_belief("AAPL-[observed_with]->$310.52")
    assert not is_actionable_belief("NVDA-[observed_with]->1,234,567")
    assert is_actionable_belief("AI capex drives NVDA outperformance")


def test_us_market_session_weekend():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from acme.quant.market_hours import us_market_session

    sat = datetime(2026, 6, 27, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    session = us_market_session(sat)
    assert session["open"] is False
    assert session["status"] == "weekend"


def test_us_market_session_open():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from acme.quant.market_hours import us_market_session

    tue = datetime(2026, 6, 24, 11, 0, tzinfo=ZoneInfo("America/New_York"))
    session = us_market_session(tue)
    assert session["open"] is True
    assert session["status"] == "open"


def test_quant_trading_session_crypto_24_7():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from acme.quant.market_hours import quant_trading_session

    sat = datetime(2026, 6, 27, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    session = quant_trading_session(crypto_enabled=True, now=sat)
    assert session["open"] is True
    assert session["crypto_active"] is True
    assert session["equities_open"] is False
    assert session["status"] == "crypto_only"


def test_is_crypto_symbol():
    from acme.quant.symbols import crypto_base, is_crypto

    assert is_crypto("BTC-USD")
    assert not is_crypto("AAPL")
    assert crypto_base("ETH-USD") == "ETH"


def test_belief_matches_crypto():
    from acme.quant.symbols import belief_matches_symbol

    assert belief_matches_symbol("BTC volatility drives risk-off", "BTC-USD")
    assert belief_matches_symbol("AAPL earnings beat", "AAPL")


def test_merge_mark_prices_prefers_intraday():
    from acme.quant.scalp import merge_mark_prices

    intraday = {"AAPL": [{"close": 310.5}]}
    daily = {"AAPL": 308.63, "MSFT": 390.0}
    merged = merge_mark_prices(["AAPL", "MSFT"], intraday, daily)
    assert merged["AAPL"] == 310.5
    assert merged["MSFT"] == 390.0


@pytest.mark.asyncio
async def test_quote_cache_returns_cached_without_refetch():
    from acme.quant.market import QuoteCache

    cache = QuoteCache(ttl_sec=300)
    sample = [{"symbol": "AAPL", "price": 100.0, "change_pct": 1.0, "volume": 1, "market_cap": None, "timestamp": datetime.now(timezone.utc)}]

    async def fake_refresh(symbols):
        return sample

    cache._refresh = fake_refresh  # type: ignore[method-assign]
    cache._quotes = sample
    cache._symbols_key = ("AAPL",)
    cache._fetched_at = datetime.now(timezone.utc)

    with patch("acme.quant.market._fetch_quotes_batch_sync") as mock_fetch:
        result = await cache.get(["AAPL"])
        assert result[0]["symbol"] == "AAPL"
        mock_fetch.assert_not_called()

