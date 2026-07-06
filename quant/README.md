# ACME Quant — Belief-Driven Paper Trading

**Industry-standard quantitative research demo powered by ACME cognitive memory.**

Live dashboard: `/api/v1/quant/` (when `QUANT_DEMO_ENABLED=true`)

---

## What this is

ACME Quant is a **public research showcase** that connects real market data, news ingestion, and ACME's belief engine to a **paper trading account**. Every trade is traceable back to episodic evidence, graph relations, and CRS-scored beliefs — with a dashboard to audit the full reasoning trail.

This is **not** live trading. It runs on a demo account with real prices (Yahoo Finance) and is designed to be **copy-trade ready**: signals and fills are exported via API for followers who want to mirror the strategy on their own broker.

---

## Cognitive loop

```
Real market data (yfinance)          News headlines (RSS)
         │                                    │
         └──────────────┬─────────────────────┘
                        ▼
              Experience ingestion
         (episodes → Neo4j graph → beliefs)
                        │
                        ▼
              Research agent query
    "Given beliefs + context, any actionable thesis?"
                        │
                        ▼
              Prediction + paper order
         (linked to belief_graph_id for audit)
                        │
                        ▼
              Outcome feedback → CRS update
                        │
                        ▼
              Dashboard: portfolio + belief trail
```

### Belief promotion pipeline

Same as core ACME:

| Stage | Example |
|-------|---------|
| **Observation** | `NVDA +4.2% on 48M volume after earnings beat` |
| **Inference** | `AI capex cycle accelerating` |
| **Hypothesis** | `Semiconductor leaders outperform SPY over 30d` |
| **Belief** | Promoted when evidence + prediction success thresholds met |

CRS (Confidence Reliability Score) weights prediction accuracy, temporal stability, contradiction resistance, and source diversity.

---

## Architecture

```
quant/                          ← this README
acme/quant/
  market.py                     Real quotes & bars (yfinance)
  news.py                       Headline ingestion (Yahoo RSS)
  paper_broker.py               Paper account, positions, fills
  trace.py                      Belief reasoning trail builder
  service.py                    Background research cycle
  routes.py                     REST API + dashboard static
  static/                       Dashboard SPA
```

### Data stores

| Store | Contents |
|-------|----------|
| **PostgreSQL** | Episodes, beliefs, predictions, paper trades, portfolio snapshots |
| **Neo4j** | Entity graph (`NVDA`, `Fed`, `rate hike`) with typed relations |
| **Event log** | Append-only audit trail |

### Tenant isolation

Default showcase tenant: `quant-demo`. Each visitor session can optionally get `quant-{uuid}` for isolated sandboxes.

---

## API reference

Base path: `/api/v1/quant`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard UI |
| `GET` | `/state` | Full dashboard payload (portfolio, beliefs, quotes, trace) |
| `GET` | `/portfolio` | Cash, positions, NAV, P&L |
| `GET` | `/trades` | Trade blotter with belief links |
| `GET` | `/beliefs` | Active market beliefs (CRS sorted) |
| `GET` | `/trace` | Reasoning trail (`TraceOut`: nodes, edges, steps) |
| `GET` | `/quotes` | Live quotes for watchlist |
| `GET` | `/signals` | Copy-trade export (recent actionable signals) |
| `POST` | `/cycle` | Trigger one research cycle manually |
| `POST` | `/reset` | Reset paper account + tenant memory |

### Copy-trade signal format

```json
{
  "signals": [
    {
      "id": "uuid",
      "symbol": "NVDA",
      "side": "buy",
      "quantity": 10,
      "price": 875.42,
      "timestamp": "2026-07-06T10:30:00Z",
      "belief_id": "relation:abc123",
      "belief_label": "AI capex drives NVDA outperformance",
      "crs": 0.72,
      "reasoning": "Promoted belief + positive earnings momentum"
    }
  ]
}
```

Integrators poll `GET /signals?since=ISO8601` and mirror on their broker. **Demo only — not investment advice.**

---

## Configuration

```env
QUANT_DEMO_ENABLED=true
QUANT_TENANT_ID=quant-demo
QUANT_SYMBOLS=AAPL,MSFT,NVDA,GOOGL,AMZN,META,SPY,QQQ
QUANT_STARTING_CASH=1000000
QUANT_CYCLE_INTERVAL_SEC=300
QUANT_MAX_POSITION_PCT=0.15
QUANT_MIN_BELIEF_CRS=0.55
```

Requires core ACME services: PostgreSQL, Neo4j, LLM provider (Azure OpenAI or Ollama).

---

## Dashboard

The web UI (`/api/v1/quant/`) provides:

1. **Portfolio panel** — NAV, daily P&L, cash, positions table with unrealized P&L
2. **Market strip** — live quotes for watchlist symbols
3. **Beliefs panel** — CRS-scored theses with status badges
4. **Reasoning trail** — scrubbable graph showing observation → hypothesis → belief → trade
5. **Trade blotter** — fills linked to beliefs
6. **Copy-trade feed** — exportable signals

Dark terminal aesthetic, mobile-responsive, no framework dependencies.

---

## Research cycle (background)

Every `QUANT_CYCLE_INTERVAL_SEC` seconds (default 5 min):

1. **Ingest** — fetch quotes + news for watchlist symbols
2. **Extract** — ACME LLM extracts entities/relations into Neo4j
3. **Sync beliefs** — BeliefEngine promotes/demotes based on evidence
4. **Research** — agent queries memory: actionable thesis?
5. **Trade** — if CRS ≥ threshold, paper market order (max 15% NAV per position)
6. **Snapshot** — record portfolio NAV for equity curve
7. **Validate** — check pending predictions against realized prices

---

## Development

```bash
# Enable quant demo
export QUANT_DEMO_ENABLED=true

# Start infrastructure
docker compose up -d

# Run API
uvicorn acme.main:app --reload

# Open dashboard
open http://localhost:8000/api/v1/quant/

# Trigger manual cycle
curl -X POST http://localhost:8000/api/v1/quant/cycle

# Run tests
pytest tests/test_quant.py -v
```

---

## Roadmap

- [ ] Alpaca / IBKR paper API adapter (optional broker backend)
- [ ] SSE live updates for dashboard
- [ ] Sector rotation & macro regime detection
- [ ] Multi-strategy tenants (value, momentum, macro)
- [ ] Sharpe / drawdown analytics panel
- [ ] Webhook push for copy-trade followers

---

## Disclaimer

**This is a research demonstration.** Paper trading with real market data. Not financial advice. Past simulated performance does not guarantee future results. Use at your own risk.
