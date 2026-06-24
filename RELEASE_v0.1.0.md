# ACME v0.1.0-azure (arxiv-ready)

**Date:** 2026-06-24  
**API:** https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io  
**Revision:** `acme-api--neo4jfix2`  
**Repo:** https://github.com/KamilBourouiba/ACME

## MemoryBench v3 (13 scenarios, prod, June 2026)

| System | Overall |
|--------|---------|
| **ACME** | **0.925** |
| RAG | 0.487 |
| MemGPT | 0.487 |
| LangGraph | 0.469 |

*Run job `3b31e5e3`, 24 June 2026. See `docs/BENCHMARK_RESULTS.md`.*

ACME retention/groundedness/feedback: **1.000** · belief quality: **0.700** · failures: **none**

Reproduce: `./azure/configure-premium-ingress.sh && ./scripts/run_prod_benchmark.sh`

## Stack

- Azure OpenAI GPT-4.1 + `text-embedding-3-small` (256D)
- Postgres Flexible (francecentral) + pgvector
- Neo4j tenant-scoped graph (`tenant_id`, composite unique key)
- Premium ingress (30 min) for benchmarks; ~$100/mo budget — see `docs/AZURE_COSTS.md`
- API key on benchmark endpoints (`azure/set-api-key.sh`)

## arXiv

- Manuscript: `docs/PAPER.md`
- PDF: `docs/PAPER.pdf` (`./scripts/export_paper_pdf.sh`)
- Checklist: `docs/ARXIV_SUBMISSION.md`

## Docs

- [README.md](README.md)
- [docs/BASELINES.md](docs/BASELINES.md)
- [docs/AZURE_COSTS.md](docs/AZURE_COSTS.md)
