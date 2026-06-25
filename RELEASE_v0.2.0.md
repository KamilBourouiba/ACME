# ACME v0.2.0-longmemeval

**Date:** 2026-06-25  
**API:** https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io  
**Image:** `acme-api:longmemeval-transcript`  
**Repo:** https://github.com/KamilBourouiba/ACME

## MemoryBench v3 (13 scenarios, prod)

| System | Overall |
|--------|---------|
| **ACME** | **0.925** |
| RAG | 0.487 |

*Job `3b31e5e3`, 24 June 2026.*

## LongMemEval oracle (500 Q, prod, June 2026)

| System | Overall | KU | Multi-session | Temporal |
|--------|---------|-----|---------------|----------|
| **ACME** | **0.804** | **0.897** | 0.744 | **0.684** |
| MemGPT | 0.780 | 0.872 | 0.752 | 0.609 |
| RAG | 0.776 | 0.859 | **0.789** | 0.602 |

*Jobs `705eb2ff` (78 KU) + `26e288da` (422 other types). Transcript-first path for LongMemEval adapter.*

Reproduce: `./azure/configure-premium-ingress.sh && bash scripts/run_longmemeval_prod.sh`

## What's new

- Official LongMemEval adapter (`acme/evaluation/longmemeval.py`) + async prod API
- Transcript-first answering (newest-first sessions) for knowledge-update resolution
- Belief demotion on superseded sources during KU ingest
- Paper v1.3: full LongMemEval tables + limitations (multi-session, abstention, routing)

## Docs

- [docs/LONGMEMEVAL.md](docs/LONGMEMEVAL.md)
- [docs/BENCHMARK_RESULTS.md](docs/BENCHMARK_RESULTS.md)
- [docs/PAPER.pdf](docs/PAPER.pdf) — `./scripts/export_paper_pdf.sh`
- [docs/ARXIV_SUBMISSION.md](docs/ARXIV_SUBMISSION.md) — checklist (not yet submitted)
