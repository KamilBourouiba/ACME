# ACME v0.1.0-azure

**Date:** 2026-06-24  
**API:** https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io  
**Revision:** `acme-api--pgflex-*` (Azure Postgres Flexible + pgvector, francecentral)

## Highlights

- MemoryBench v2: **10 scenarios**, sandbox-isolated (Postgres + Neo4j)
- Production scores (GPT-4.1, Azure OpenAI embeddings 256D):
  - **ACME overall 0.925** (retention 0.980, groundedness 1.000, belief 0.700)
  - RAG 0.482 · MemGPT 0.482 · LangGraph 0.485
- Azure OpenAI `text-embedding-3-small` deployment + pgvector on Flexible Server
- Persisted benchmark runs, CI gates (`BENCHMARK_MIN_OVERALL=0.85`)
- Consolidation worker (6h cron), premium ingress (30 min timeout)
- Compare async endpoint + export

## Deploy

```bash
./azure/deploy.sh
./azure/embedding-deploy.sh
FALLBACK_LOCATION=francecentral ./azure/postgres-flexible.sh
./azure/configure-premium-ingress.sh
./azure/consolidation-job.sh
```

## Tests

```bash
make test
BENCHMARK_MIN_OVERALL=0.85 BENCHMARK_MIN_BELIEF_QUALITY=0.55 pytest tests/test_benchmark_gate.py -q
```

## Docs

- [README.md](README.md)
- [docs/PAPER.md](docs/PAPER.md)
- [docs/BASELINES.md](docs/BASELINES.md)
- [docs/ARXIV_SUBMISSION.md](docs/ARXIV_SUBMISSION.md)
