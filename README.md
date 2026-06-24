# ACME: Adaptive Cognitive Memory Engine

**Externalizing memory, belief, and learning from LLM weights into an auditable cognitive substrate.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Website](https://img.shields.io/badge/website-project%20site-cyan.svg)](https://kamilbourouiba.github.io/ACME/)

**Project site:** https://kamilbourouiba.github.io/ACME/

---

## Abstract

Large language models encode knowledge implicitly in static weights. They lack durable episodic memory, explicit belief states, structured forgetting, and mechanisms to learn from failure. **ACME** (Adaptive Cognitive Memory Engine) treats the LLM as a *language and reasoning processor* while delegating persistence, confidence tracking, abstraction, and self-correction to an external memory architecture.

Given an experience stream, ACME (1) extracts typed knowledge into a semantic graph, (2) retrieves graph-backed context for reasoning, (3) challenges high-confidence answers via a contrarian pass, (4) updates beliefs from outcome feedback, (5) compresses episode clusters into abstractions, (6) manages memory lifecycle through importance-weighted forgetting, and (7) autonomously generates testable hypotheses from accumulated evidence.

The central research question ACME operationalizes is:

> *When does a collection of experiences deserve to become a belief?*

We address this with a promotion pipeline (`Observation → Inference → Hypothesis → Belief`) governed by evidence thresholds, failure logging, and confidence decay—moving beyond retrieval-augmented generation toward **adaptive cognitive memory**.

---

## Motivation

| Limitation of standard LLM stacks | ACME response |
|-----------------------------------|---------------|
| Knowledge frozen in pre-training weights | External episodic + semantic memory |
| No explicit belief system | Belief engine with promotion thresholds |
| Weak long-term memory | PostgreSQL episodic store + Neo4j graph |
| No structured forgetting | Tiered lifecycle: HOT → WARM → COLD → ARCHIVE → DELETE |
| Limited learning from failures | Failure engine + feedback-driven confidence updates |
| Vector-only retrieval | Hybrid graph + pgvector (JSONB fallback) |
| Unchecked self-confidence | Contrarian engine on high-confidence outputs |

---

## Architecture

```
                         ┌─────────────────────────────────────┐
                         │           LLM Provider              │
                         │   (Azure OpenAI / Ollama / …)         │
                         │  extraction · reasoning · abstraction │
                         └──────────────┬──────────────────────┘
                                        │
    Experience ──► ┌────────────────────▼────────────────────┐
                   │              Orchestrator                  │
                   │         (self-improvement loop)            │
                   └─┬──────┬──────┬──────┬──────┬──────┬──────┘
                     │      │      │      │      │      │
              ┌──────▼──┐ ┌─▼───┐ ┌▼────┐ ┌▼────┐ ┌▼────┐ ┌▼──────┐
              │ Episodic │ │Graph│ │Belief│ │Fail.│ │Comp.│ │Learn. │
              │  Store   │ │Mem. │ │Eng.  │ │Eng. │ │Eng. │ │Eng.   │
              │ Postgres │ │Neo4j│ │      │ │     │ │     │ │       │
              └──────┬───┘ └──┬──┘ └──┬───┘ └──┬──┘ └──┬──┘ └───┬───┘
                     │        │       │        │       │        │
                     └────────┴───────┴────────┴───────┴────────┘
                                    Event Store
                              (append-only, PostgreSQL)
```

### Cognitive loop

```
Question
   ↓
Reasoning (LLM + graph context)
   ↓
Memory Graph retrieval
   ↓
Contrarian check (if confidence ≥ 0.8)
   ↓
Confidence evaluation
   ↓
Answer
   ↓
Outcome feedback
   ↓
Failure log · Belief update · Compression · Forgetting · Hypothesis generation
```

---

## Knowledge typology

ACME distinguishes four epistemic levels to mitigate false causal inference (e.g., *A preceded B* ≠ *A caused B*):

```
Observation  →  Inference  →  Hypothesis  →  Belief
   (raw)        (derived)     (testable)     (promoted)
```

### Belief promotion criteria

A hypothesis is promoted to **Belief** when all of the following hold:

| Criterion | Default threshold |
|-----------|-------------------|
| Supporting observations | ≥ 3 |
| Distinct time windows | ≥ 2 |
| Support ratio | ≥ 0.7 |
| Prediction success rate | ≥ 0.6 (when predictions exist) |

Configurable via environment variables (`BELIEF_MIN_*`).

### Belief lifecycle (promotion & demotion)

ACME applies symmetric demotion when contradictory evidence accumulates:

```
Observation → Hypothesis → Belief → Challenged → Deprecated → Archived
```

| Evidence pattern | Effect |
|------------------|--------|
| Repeated supporting observations | Confidence ↑, promotion toward **Belief** |
| 1 strong contradiction | Significant confidence drop; status → **Challenged** |
| ≥ 3 independent contradictions | Status → **Deprecated** |
| ≥ 5 contradictions | Status → **Archived** |

Thresholds: `BELIEF_DEMOTE_CONTRADICTIONS`, `BELIEF_ARCHIVE_CONTRADICTIONS`, `BELIEF_STRONG_CONTRADICTION_PENALTY`.

### Cognitive Reliability Score (CRS)

Each belief receives a composite **Cognitive Reliability Score** for objective comparison:

```
CRS = 40% prediction success
    + 20% temporal stability (time windows)
    + 20% contradiction resistance
    + 20% independent source diversity
```

Weights: `CRS_WEIGHT_*` environment variables.

### Causal relation typing

Graph edges carry explicit causal semantics to reduce correlation/causation errors:

| `causal_type` | Meaning |
|---------------|---------|
| `observed_with` | Co-occurrence without causal claim |
| `precedes` | Temporal ordering |
| `correlates` | Statistical association |
| `causes` | Explicit causal claim (strict) |
| `disproves` | Contradictory evidence link |

Deterministic pattern extraction merges with LLM output to reduce model dependency for structured fields.

### Independent sources

Experiences carry `source_type` (`user`, `database`, `api`, `web`, `sensor`, `human_expert`) and optional `source_id`. Belief confidence is weighted by `source_credibility × evidence`; three independent sources outweigh twenty observations from the same stream.

### Predictive validation loop

```
experience → hypothesis → prediction → validation → belief
```

Use `POST /api/v1/predictions` and `POST /api/v1/predictions/validate` to register testable forecasts and update belief CRS from outcomes.

---

## Engine modules

| Engine | Function |
|--------|----------|
| **Extraction** | LLM-driven entity/relation extraction into typed graph nodes |
| **Retrieval** | Hybrid graph + vector (pgvector or JSONB cosine) with cross-verification |
| **Belief** | Confidence tracking, CRS, promotion/demotion lifecycle, source weighting |
| **Prediction** | Testable forecasts linked to hypotheses/beliefs |
| **Meta-learning** | Metrics on promotion/deprecation rates and learning quality |
| **Deterministic** | Rule-based extraction, causal typing, cognitive profiles |
| **Failure** | Classification: data / reasoning / memory / execution failures |
| **Contrarian** | Evidence-based challenge of high-confidence conclusions |
| **Compression** | Cluster episodes by tag; LLM abstraction with confidence gate |
| **Forgetting** | Importance = confidence × usage × recency × outcome impact |
| **Learning** | Autonomous consolidation + hypothesis generation cycle |

### Memory lifecycle

```
HOT  →  WARM  →  COLD  →  ARCHIVE  →  DELETE
 ↑        ↑        ↑         ↑            ↑
recent   moderate  stale    content      only if archived
access   access            preserved    + low importance
```

Archive always precedes deletion. Content is preserved in `archived_content` before active retrieval is disabled.

---

## LLM provider abstraction

ACME decouples inference from memory. The LLM never owns persistent state; all outputs pass through verification layers.

| Provider | Use case |
|----------|----------|
| `azure_openai` | Production (e.g. GPT-4.1 deployment) |
| `ollama` | Local development |

Set `LLM_PROVIDER` and provider-specific credentials. Structured tasks (extraction, reasoning, compression, hypothesis generation) use JSON-mode when supported.

---

## Comparison

| Capability | RAG | Agent memory | **ACME** |
|------------|-----|--------------|----------|
| Episodic log | partial | ✓ | ✓ |
| Typed semantic graph | ✗ | partial | ✓ |
| Belief confidence | ✗ | ✗ | ✓ |
| Failure-driven learning | ✗ | partial | ✓ |
| Contrarian verification | ✗ | ✗ | ✓ |
| Experience compression | ✗ | ✗ | ✓ |
| Structured forgetting | ✗ | ✗ | ✓ |
| Autonomous hypotheses | ✗ | ✗ | ✓ |
| Event-sourced audit trail | ✗ | partial | ✓ |

---

## Quick start

### Local (Docker + Ollama)

```bash
git clone <repo> && cd ACME
cp .env.example .env
docker compose up -d

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn acme.main:app --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### Local (Azure OpenAI)

```bash
cp .env.example .env
# LLM_PROVIDER=azure_openai
# AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
# AZURE_OPENAI_API_KEY=<key>
# AZURE_OPENAI_DEPLOYMENT=gpt-4.1
make dev
```

### Azure deployment

```bash
chmod +x azure/deploy.sh
./azure/deploy.sh
# Override: OPENAI_RG=... OPENAI_ACCOUNT=... OPENAI_DEPLOYMENT=gpt-4.1
```

Deploys Container Apps (API + PostgreSQL `pgvector/pgvector:pg16` + Neo4j) wired to an existing Azure OpenAI deployment. See `azure/deployment.env` after deploy.

Optional scripts:

```bash
./azure/deploy.sh
./azure/embedding-deploy.sh              # text-embedding-3-small on Azure OpenAI
FALLBACK_LOCATION=francecentral ./azure/postgres-flexible.sh
./azure/configure-premium-ingress.sh   # 30 min idle timeout for long benchmarks
./azure/consolidation-job.sh           # Cron consolidation (every 6h)
```

**Production (Azure, June 2026):** `https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io` — Postgres Flexible (`acme-pg-flex`, francecentral) + pgvector, GPT-4.1, Azure embeddings `text-embedding-3-small` (256D).

See [RELEASE_v0.1.0.md](RELEASE_v0.1.0.md), [docs/BASELINES.md](docs/BASELINES.md), [docs/ARXIV_SUBMISSION.md](docs/ARXIV_SUBMISSION.md). Repo: https://github.com/KamilBourouiba/ACME

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Service health + LLM provider status |
| `POST` | `/api/v1/experiences` | Ingest episodic experience |
| `POST` | `/api/v1/query` | Graph-backed reasoning query |
| `POST` | `/api/v1/feedback` | Outcome feedback on a session |
| `GET` | `/api/v1/beliefs` | List tracked beliefs |
| `POST` | `/api/v1/compress` | Compress episode clusters |
| `GET` | `/api/v1/abstractions` | List abstractions |
| `POST` | `/api/v1/forget/run` | Run forgetting cycle |
| `GET` | `/api/v1/episodes` | List episodes by memory tier |
| `POST` | `/api/v1/learn/run` | Autonomous learning cycle |
| `GET` | `/api/v1/hypotheses` | Generated hypotheses |
| `GET` | `/api/v1/learn/cycles` | Learning cycle history |
| `POST` | `/api/v1/predictions` | Register testable prediction |
| `POST` | `/api/v1/predictions/validate` | Validate prediction outcome |
| `GET` | `/api/v1/predictions` | List predictions |
| `POST` | `/api/v1/contradictions` | Record contradiction against a belief |
| `GET` | `/api/v1/meta-learning` | Meta-learning metric snapshot |
| `GET` | `/api/v1/metrics` | Operational metrics (beliefs, CRS, episodes) |
| `POST` | `/api/v1/benchmark/memorybench` | Run MemoryBench v3 (13 scenarios, isolated sandbox) |
| `POST` | `/api/v1/benchmark/compare` | ACME vs RAG / MemGPT / LangGraph (~5 min) |
| `POST` | `/api/v1/benchmark/compare/async` | Start compare job (poll `.../jobs/{id}`) |
| `GET` | `/api/v1/benchmark/compare/jobs/{job_id}` | Compare job status + result |
| `GET` | `/api/v1/benchmark/runs/latest` | Latest persisted benchmark run |
| `GET` | `/api/v1/benchmark/export` | Export JSON of latest compare run |
| `POST` | `/api/v1/causal/validate` | Intervention-based causal validation |
| `POST` | `/api/v1/consolidation/run` | Full consolidation + predictions worker target |
| `GET` | `/api/v1/graph/entities/{name}` | Graph neighborhood |
| `GET` | `/api/v1/sessions/{session_id}` | Query session detail |

### Minimal cognitive loop

```bash
# 1. Ingest
curl -X POST http://localhost:8000/api/v1/experiences \
  -H "Content-Type: application/json" \
  -d '{"content":"Customer churned after repeated API latency.","action":"analyze","tags":["latency","churn"]}'

# 2. Query
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Why do customers churn?","challenge":true}'

# 3. Feedback
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<uuid>","outcome":"success","feedback":"Confirmed"}'

# 4. Consolidate
curl -X POST http://localhost:8000/api/v1/learn/run \
  -H "Content-Type: application/json" \
  -d '{"consolidate":true,"generate_hypotheses":true,"forget_dry_run":true}'
```

---

## Evaluation: MemoryBench

**MemoryBench** quantifies cognitive memory quality across four dimensions:

| Metric | What it measures |
|--------|------------------|
| Retention | Semantic recall — LLM judge scores concept coverage (synonyms count) |
| Feedback correction | Belief adjustment after outcome feedback / contradictions |
| Hallucination resistance | Groundedness — answer supported by ingested episodes |
| Belief quality | Average CRS across tracked beliefs |

Scoring uses an **LLM-as-judge** (`evaluate_answer_quality`) with deterministic synonym fallback. Legacy keyword overlap is reported in `details.keyword_retention_avg` for comparison.

```bash
curl -X POST http://localhost:8000/api/v1/benchmark/memorybench
```

Scenarios live in `acme/evaluation/memorybench.py` (**13 scenarios**, sandbox-isolated per run). Compare against baselines:

```bash
curl -X POST http://localhost:8000/api/v1/benchmark/memorybench
curl -X POST http://localhost:8000/api/v1/benchmark/compare          # sync (~5 min)
curl -X POST http://localhost:8000/api/v1/benchmark/compare/async    # async + poll job
curl http://localhost:8000/api/v1/benchmark/runs/latest
python scripts/investor_demo.py --url http://localhost:8000
python scripts/consolidation_worker.py --url http://localhost:8000
```

Academic draft: [docs/PAPER.md](docs/PAPER.md)

---

```
acme/
├── main.py                 # FastAPI application
├── orchestrator.py         # Self-improvement loop coordinator
├── config.py               # Thresholds & provider settings
├── schemas.py              # Pydantic models
├── api/routes.py           # REST endpoints
├── db/models.py            # Episodic store, beliefs, failures, hypotheses
├── events/store.py         # Append-only event log
├── graph/neo4j_client.py   # Semantic graph projection
├── evaluation/
│   ├── memorybench.py      # MemoryBench v2 scenarios & runner
│   ├── comparison.py       # ACME vs baseline compare
│   ├── benchmark_store.py  # Persist runs to Postgres
│   └── sandbox.py          # Per-scenario isolation cleanup
├── llm/
│   ├── base.py             # Shared LLM interface + task prompts
│   ├── azure_openai.py     # Azure OpenAI provider
│   ├── ollama.py           # Ollama provider
│   ├── embeddings.py       # Azure OpenAI or deterministic embeddings
│   └── factory.py          # Provider selection
└── engines/
    ├── belief.py           # CRS, lifecycle, source-aware confidence
    ├── vector_retrieval.py # pgvector + JSONB fallback
    ├── hybrid_retrieval.py # Graph + vector merge
    ├── deterministic.py    # Rule-based extraction & causal typing
    ├── prediction.py       # Prediction → validation loop
    ├── meta_learning.py    # Learning-about-learning metrics
    ├── extraction.py       # LLM + deterministic merge
    ├── compression.py      # Pattern → abstraction
    ├── forgetting.py       # Memory lifecycle
    ├── learning.py         # Autonomous hypotheses
    ├── failure.py          # Failure taxonomy
    └── retrieval.py        # Graph context assembly
benchmarks/
└── memorybench/runner.py   # Backward-compatible re-exports
azure/
├── deploy.sh               # Container Apps deploy
├── configure-premium-ingress.sh
├── consolidation-job.sh
└── postgres-flexible.sh    # Optional managed Postgres + pgvector
```

---

## Testing

```bash
make test                              # Unit tests (55+)
RUN_INTEGRATION=1 make test-integration  # E2E (Docker + LLM)
python scripts/demo.py                 # Full loop demo
```

CI (`.github/workflows/ci.yml`) runs unit tests against `pgvector/pgvector:pg16` and enforces benchmark gates via `acme/evaluation/benchmark_gate.py`.

---

## Known limitations

- **Graph scaling**: semantic graph growth requires ongoing compression and entity merging (partially addressed by compression + forgetting engines).
- **Causal inference**: mitigated by explicit `causal_type` on edges and deterministic normalization; `causes` requires explicit linguistic evidence.
- **Confidence inflation**: mitigated by CRS, multi-source requirements, demotion lifecycle, and contrarian checks.
- **Multi-tenant isolation**: Postgres, API routes, and Neo4j graph entities are scoped via `X-Tenant-ID` (composite key `tenant_id + name` in Neo4j).
- **pgvector**: enabled on container Postgres (`pgvector/pgvector:pg16`); SQLAlchemy casts use `CAST(:vec AS vector)` (not `:vec::vector`). Falls back to JSONB cosine when the extension or column update fails.

---

## Benchmarks

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/benchmark/memorybench` | MemoryBench v3 — 13 scenarios, isolated sandbox |
| `POST /api/v1/benchmark/compare` | ACME vs RAG, MemGPT, LangGraph (~5 min; needs premium ingress on Azure) |
| `POST /api/v1/benchmark/compare/async` | Compare in background — poll `GET .../compare/jobs/{id}` |
| `GET /api/v1/benchmark/runs/latest` | Latest persisted run (Postgres `benchmark_runs`) |
| `GET /api/v1/benchmark/export` | JSON export of latest compare run |
| `GET /api/v1/metrics` | Operational metrics (CRS, beliefs, episodes) |

Optional: set `API_KEY` env + `X-API-Key` header (prod: `./azure/set-api-key.sh`); benchmark endpoints rate-limited (`BENCHMARK_RATE_LIMIT_PER_HOUR`, default 10/hour).

Ablation env vars: `ABLATION_DISABLE_CONTRARIAN`, `ABLATION_DISABLE_BELIEF_SYNC`, `ABLATION_DISABLE_VECTOR`.

### Latest Azure results (GPT-4.1, June 2026, 10 scenarios, isolated)

| System | Retention | Groundedness | Feedback | Belief Q. | Overall |
|--------|-----------|--------------|----------|-----------|---------|
| **ACME** | **1.000** | **1.000** | **1.000** | **0.700** | **0.925** |
| RAG baseline | 0.960 | 0.980 | N/A | N/A | 0.481 |
| MemGPT baseline | 0.970 | 0.950 | N/A | N/A | 0.467 |
| LangGraph baseline | 0.960 | 0.970 | N/A | N/A | 0.488 |

*Baselines exclude feedback/belief dimensions (not applicable). Run `POST /benchmark/compare` or `/compare/async` to refresh.*

CI gate thresholds: `BENCHMARK_MIN_OVERALL=0.85`, `BENCHMARK_MIN_BELIEF_QUALITY=0.55`.

---

## Future work

- arXiv publication of `docs/PAPER.md`
- Official MemGPT/LangGraph baseline implementations
- Neo4j per-tenant graph partitioning

---

## Citation

If you use ACME in your research, please cite:

```bibtex
@software{acme2025,
  title        = {ACME: Adaptive Cognitive Memory Engine},
  author       = {{ACME Contributors}},
  year         = {2025},
  url          = {https://github.com/<org>/ACME},
  note         = {External memory architecture for belief-driven LLM systems}
}
```

---

## License

MIT — see [LICENSE](LICENSE).
