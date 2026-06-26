# ACME v0.3.0-longmemeval-v5

**Date:** 2026-06-26  
**API:** https://acme-api.blackgrass-3076f328.westeurope.azurecontainerapps.io  
**Image:** `acme-api:longmemeval-v5-hybrid`  
**Repo:** https://github.com/KamilBourouiba/ACME

## MemoryBench v3 (13 scenarios)

| System | Overall |
|--------|---------|
| **ACME** | **0.925** |
| RAG | 0.487 |

Job `3b31e5e3`, GPT-4.1, June 2026.

## LongMemEval oracle (500 Q, single clean run)

| System | Overall | KU | Multi-session | Temporal | Preference | Abstention |
|--------|---------|-----|---------------|----------|------------|------------|
| **ACME** | **0.876** | **0.944** | 0.793 | **0.803** | 0.900 | **0.833** |
| MemGPT | 0.786 | 0.861 | 0.793 | 0.630 | 0.600 | 0.600 |
| RAG | 0.776 | 0.875 | 0.793 | 0.622 | 0.467 | 0.600 |

Job `45623ca0`, ~6.2 h, zero errors.

Reproduce: `LONGMEMEVAL_TYPES=all bash scripts/run_longmemeval_prod.sh`

## What's new

- **v4:** per-type routing (KU, multi-session, temporal, abstention, preference)
- **v5:** temporal timeline precompute, abstention anchor short-circuit, graph-vector multi-session hybrid
- Paper + benchmark docs updated with canonical 500 Q scores

## Docs

- [docs/LONGMEMEVAL.md](docs/LONGMEMEVAL.md)
- [docs/PAPER.pdf](docs/PAPER.pdf)
- [docs/ARXIV_SUBMISSION.md](docs/ARXIV_SUBMISSION.md)
