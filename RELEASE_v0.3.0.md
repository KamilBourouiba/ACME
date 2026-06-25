# ACME v0.3.0-longmemeval-v5

**Date:** 2026-06-25  
**API:** https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io  
**Image:** `acme-api:longmemeval-v5-hybrid`  
**Repo:** https://github.com/KamilBourouiba/ACME

## MemoryBench v3 (13 scenarios)

| System | Overall |
|--------|---------|
| **ACME** | **0.925** |
| RAG | 0.487 |

Job `3b31e5e3`, GPT-4.1, June 2026.

## LongMemEval oracle (500 Q)

> **Pending:** full clean v5 run (`LONGMEMEVAL_TYPES=all`). Interim v4 combined: ACME **0.848** vs RAG **0.780**.

| System | Overall | KU | Multi | Temporal | Preference | Abstention |
|--------|---------|-----|-------|----------|------------|------------|
| **ACME** | *v5 TBD* | *TBD* | *TBD* | *TBD* | *TBD* | *TBD* |

Reproduce: `LONGMEMEVAL_TYPES=all bash scripts/run_longmemeval_prod.sh`

## What's new in v0.3.0

- Per-type LongMemEval routing (v4): KU, multi-session, temporal, abstention, preference
- v5 hybrid: temporal timeline precompute, abstention anchor short-circuit, graph-vector multi-session context
- `LONGMEMEVAL_TYPES=all` for full 500 Q prod benchmark
- Paper + `docs/BENCHMARK_RESULTS.md` updated after v5 job completes

## Docs

- [docs/LONGMEMEVAL.md](docs/LONGMEMEVAL.md)
- [docs/PAPER.pdf](docs/PAPER.pdf)
- [docs/ARXIV_SUBMISSION.md](docs/ARXIV_SUBMISSION.md)
