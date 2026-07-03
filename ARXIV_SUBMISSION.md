# arXiv submission checklist — ACME v1.3

**Source manuscript:** `docs/PAPER.md`  
**PDF:** `docs/PAPER.pdf` (generate: `./scripts/export_paper_pdf.sh`)  
**Release:** https://github.com/KamilBourouiba/ACME/releases/tag/v0.3.0-longmemeval-v5

## Pre-submission checklist

- [x] Manuscript structure (abstract, methods, results, limitations, reproduction appendix)
- [x] MemoryBench scoring: N/A in tables, **0** in four-metric capability index (documented)
- [x] Bootstrap CIs for all systems (Table 9) + archived export `docs/benchmarks/job-3b31e5e3-export.json`
- [x] Human audit sample `docs/HUMAN_AUDIT_MEMORYBENCH.md`
- [x] Threats to validity paragraph in limitations
- [x] GPT-5.4 removed from manuscript (repo-only in `docs/BENCHMARK_RESULTS.md`)
- [x] Baseline methodology in `docs/BASELINES.md`
- [x] **Author:** Mohamed Kamil Bourouiba
- [x] Scores match `docs/BENCHMARK_RESULTS.md` (job `3b31e5e3`, MemoryBench; job `45623ca0`, LongMemEval)
- [ ] Upload PDF to arXiv

## arXiv metadata

| Field | Value |
|-------|-------|
| **Title** | ACME: Adaptive Cognitive Memory Engine — Externalizing Belief, Memory, and Learning from LLM Weights |
| **Abstract** | Copy from `docs/PAPER.md` abstract (plain text) |
| **Categories** | Primary: **cs.AI** — Secondary: **cs.CL** |
| **Comments** | Systems preprint: belief-managed LLM agent memory; MemoryBench v3 + LongMemEval oracle 87.6%; code at https://github.com/KamilBourouiba/ACME |

## Key claims (verify before upload)

1. MemoryBench overall is a **four-metric capability index**. ACME **0.925** vs RAG-like **0.487** on GPT-4.1 (job `3b31e5e3`) because ACME is scored on feedback/belief; baselines show N/A but count as 0. Retention/groundedness are competitive ($\geq 0.90$ for most systems).
2. LongMemEval oracle **500 Q**: ACME **87.6%** vs RAG-like **77.6%** (job `45623ca0`, June 2026).
3. Frame as **open systems paper for belief-managed agent memory**, not universal SOTA.

## Submission steps (arxiv.org)

1. Create account / obtain endorsement (cs.AI) if required
2. **Submit new paper** → Upload `docs/PAPER.pdf`
3. Paste title + abstract from manuscript
4. Categories: **cs.AI** (primary), **cs.CL** (secondary)
5. Comments: "Belief-managed LLM agent memory; MemoryBench v3 + LongMemEval; code https://github.com/KamilBourouiba/ACME"
6. Submit — arXiv ID typically within 24–48h

## Post-submission

- [ ] Add arXiv ID to README citation block
- [ ] Update site footer with arXiv link
- [ ] Announce with benchmark table + link to paper PDF

## Data & code availability

> Code: https://github.com/KamilBourouiba/ACME (MIT). Benchmark payloads in Postgres `benchmark_runs`; per-scenario export in `docs/benchmarks/job-3b31e5e3-export.json`. Reproduce: `./scripts/run_prod_benchmark.sh` (Azure API key required).
