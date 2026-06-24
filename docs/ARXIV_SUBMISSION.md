# arXiv submission checklist — ACME v1.0

**Source manuscript:** `docs/PAPER.md`  
**PDF:** `docs/PAPER.pdf` (generate: `./scripts/export_paper_pdf.sh`)  
**Release:** https://github.com/KamilBourouiba/ACME/releases/tag/v0.1.0-azure

## Pre-submission checklist

- [x] Manuscript structure (abstract, methods, results, limitations, reproduction appendix)
- [x] Benchmark methodology documented (MemoryBench v3, 13 scenarios, LLM judge)
- [x] Code + tag available on GitHub
- [x] Baseline methodology in `docs/BASELINES.md`
- [ ] **Author list, affiliations, ORCID** — fill before submit
- [ ] Verify scores match latest `benchmark-results/compare-latest.json` after prod run
- [ ] Upload PDF to arXiv

## arXiv metadata

| Field | Value |
|-------|-------|
| **Title** | ACME: Adaptive Cognitive Memory Engine — Externalizing Belief, Memory, and Learning from LLM Weights |
| **Abstract** | Copy from `docs/PAPER.md` §Abstract (plain text) |
| **Categories** | Primary: **cs.AI** — Secondary: cs.CL, cs.LG |
| **Comments** | 13-page preprint; MemoryBench v3; code at https://github.com/KamilBourouiba/ACME |

## Key claims (verify against latest benchmark export)

1. ACME overall **0.925** vs RAG **0.481** on MemoryBench v3 (13 scenarios, GPT-4.1 judge, June 2026 prod run).
2. Gains driven by **feedback correction + belief quality (CRS)**, not retention alone.
3. Per-scenario **sandbox isolation** (Postgres + Neo4j) for reproducibility.

## Submission steps (arxiv.org)

1. Create account / obtain endorsement if required
2. **Submit new paper** -> Upload `docs/PAPER.pdf`
3. Paste title + abstract from manuscript
4. Select categories: cs.AI (primary), cs.CL, cs.LG
5. Add comment: "MemoryBench v3 benchmark; code https://github.com/KamilBourouiba/ACME"
6. Submit — arXiv ID assigned within ~24-48h

## Post-submission

- [ ] Add `\arxiv{XXXX.XXXXX}` to README citation block
- [ ] Update `RELEASE_v0.1.0.md` with arXiv link
- [ ] Tweet / announce with benchmark table screenshot

## Data & code availability statement (for abstract/comments)

> Code: https://github.com/KamilBourouiba/ACME (MIT). Benchmark payloads persisted in PostgreSQL `benchmark_runs`; reproduce via `./scripts/run_prod_benchmark.sh` with Azure OpenAI credentials.
