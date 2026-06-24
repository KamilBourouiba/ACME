# arXiv submission checklist — ACME v0.1.0

**Source:** `docs/PAPER.md` (draft v0.3 → promote to v0.4 at submit time)

## Pre-submission

- [ ] Update author list, affiliations, and ORCID
- [ ] Export PDF from PAPER.md (pandoc or LaTeX template)
- [ ] Verify benchmark numbers match latest `GET /benchmark/export` from prod
- [ ] Add data availability: Azure deployment URL + `benchmark_runs` table schema
- [ ] Code availability: repository URL + tag `v0.1.0-azure`

## Suggested metadata

| Field | Value |
|-------|-------|
| Title | ACME: Adaptive Cognitive Memory Engine — Externalizing Belief, Memory, and Learning from LLM Weights |
| Categories | cs.AI, cs.CL, cs.LG |
| Comments | MemoryBench v2 benchmark; code at \<repo\> |

## Key claims to keep

1. ACME overall **0.925** vs RAG **0.482** on MemoryBench v2 (10 scenarios, LLM judge).
2. Gains driven by feedback correction + belief quality (CRS), not retention alone.
3. Per-scenario sandbox isolation for reproducibility.

## Submission steps (arxiv.org)

1. Register account / obtain endorsement if required
2. Upload PDF + source (optional)
3. Paste abstract from PAPER.md §Abstract
4. Select categories cs.AI primary
5. Submit; arXiv ID will be assigned within ~24–48h

## Post-submission

- [ ] Update README citation block with arXiv ID
- [ ] Pin release notes `RELEASE_v0.1.0.md` with arXiv link
