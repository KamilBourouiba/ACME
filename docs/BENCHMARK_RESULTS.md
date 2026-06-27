# MemoryBench v3 — Production benchmark results

**Author:** Mohamed Kamil Bourouiba  
**Date:** 24 June 2026 (updated 27 June 2026 — prod deploy)  
**API revision:** `acme-api--membench-v3-fidelity` (image `acme-api:membench-v3-fidelity`)  
**Paper primary run:** job `3b31e5e3` (archived export: `docs/benchmarks/job-3b31e5e3-export.json`)  
**Reproduce:** `./scripts/run_prod_benchmark.sh` or `./scripts/deploy_membench_v3.sh` then compare async

---

## Run 1 — GPT-4.1 (primary)

| Field | Value |
|-------|-------|
| Job ID | `3b31e5e3-72b1-4ce3-b6c2-848cf94e4128` |
| Completed | 2026-06-24T18:23:06Z |
| Duration | 725 s |
| Deployment | `gpt-4.1` |
| Failures | none |

| System | Retention | Groundedness | Feedback | Belief | Overall |
|--------|-----------|--------------|----------|--------|---------|
| **ACME** | 1.000 | 1.000 | 1.000 | 0.700 | **0.925** |
| RAG | 0.969 | 0.977 | — | — | 0.487 |
| MemGPT | 0.977 | 0.969 | — | — | 0.487 |
| LangGraph | 0.900 | 0.977 | — | — | 0.469 |

**Δ ACME vs RAG:** +0.438 overall

---

## Prod deploy verification — 27 June 2026

After `./scripts/deploy_membench_v3.sh`, prod runs **13-scenario V3_SCENARIOS** (no `knowledge_update`) and **MemGPT summarize-on-evict**.

| Field | Value |
|-------|-------|
| Job ID | `9fda8d44-75d3-4cf4-bdb8-e052ebe2e1a3` |
| Revision | `acme-api--membench-v3-fidelity` |
| Duration | 687 s |
| Scenarios | **13** (all systems) |

| System | Retention | Groundedness | Overall |
|--------|-----------|--------------|---------|
| **ACME** | 0.977 | 0.977 | **0.913** |
| RAG | 0.892 | 0.977 | 0.467 |
| MemGPT-insp. | 0.969 | 0.969 | 0.485 |
| LangGraph-sty. | 0.977 | 0.985 | 0.490 |

Paper Table 8 remains on job `3b31e5e3` for publication consistency; this run confirms code parity (13 scenarios, summarize-on-evict note in export).

---

## Run 2 — GPT-4.1-mini (model sensitivity)

| Field | Value |
|-------|-------|
| Job ID | `107d02c0-e3e6-47a8-8589-e0f998dde311` |
| Completed | 2026-06-24 (poll) |
| Duration | 639 s |
| Deployment | `gpt-4.1-mini` |
| Failures | none |

| System | Retention | Groundedness | Feedback | Belief | Overall |
|--------|-----------|--------------|----------|--------|---------|
| **ACME** | 0.892 | 0.838 | 1.000 | 0.700 | **0.858** |
| RAG | 0.908 | 0.985 | — | — | 0.473 |
| MemGPT | 0.915 | 1.000 | — | — | 0.479 |
| LangGraph | 0.854 | 0.862 | — | — | 0.429 |

**Δ ACME vs RAG:** +0.385 overall

---

## Run 3 — GPT-5.4 (model sensitivity)

| Field | Value |
|-------|-------|
| Job ID | `eb68f028-e373-4cdf-a5c7-00747094300a` |
| Completed | 2026-06-24T19:27Z (approx.) |
| Duration | 620 s |
| Deployment | `gpt-5.4` (Azure OpenAI, `TESTING-CHAT-BETA`) |
| Failures | none |
| Note | Required `max_completion_tokens` API param (fixed in `acme/llm/azure_openai.py`) |

| System | Retention | Groundedness | Feedback | Belief | Overall |
|--------|-----------|--------------|----------|--------|---------|
| **ACME** | 0.952 | 0.839 | 1.000 | 0.701 | **0.873** |
| RAG | 0.964 | 0.931 | — | — | 0.474 |
| MemGPT | 0.975 | 0.939 | — | — | 0.478 |
| LangGraph | 0.973 | 0.950 | — | — | 0.481 |

**Δ ACME vs RAG:** +0.399 overall

---

## Takeaways

1. On GPT-4.1, ACME matches or exceeds baselines on retention/groundedness **and** adds full feedback/belief metrics.
2. On GPT-4.1-mini, baselines score higher on retention-only dimensions, but ACME still wins overall via feedback + belief layers.
3. On GPT-5.4, ACME reaches **0.873** overall with belief quality **0.701** — cognitive layers remain the differentiator (+0.40 vs RAG).
4. Belief quality (CRS mean) stays **~0.700** across all three models — stable cognitive substrate independent of LLM tier.

---

## MemoryBench v3.1 (14 scenarios)

| Field | Value |
|-------|-------|
| Version | `v3.1` (+ `knowledge_update` scenario, LongMemEval KU-aligned) |
| Reproduce | `POST /api/v1/benchmark/memorybench` (ACME-only, ~7 min) |
| Ablation sweep | `./scripts/run_ablation_prod.sh` |

Primary paper results (Section 6) remain on **13-scenario v3** for baseline comparability (job `3b31e5e3`).

---

## LongMemEval — knowledge-update (industry benchmark)

| Field | Value |
|-------|-------|
| Job ID | `705eb2ff-13a0-4bb8-b705-322aebb9b311` |
| Completed | 2026-06-25T03:27:34Z |
| Duration | 3510 s (~59 min) |
| API image | `acme-api:longmemeval-transcript` |
| Deployment | `gpt-4.1` |
| Subset | `knowledge-update` (78 Q: 72 KU + 6 abstention) |
| Failures | none |

| System | Overall | KU | Abstention |
|--------|---------|-----|------------|
| **ACME** (transcript-first) | **0.897** | **0.931** | 0.500 |
| MemGPT | 0.872 | 0.903 | 0.500 |
| RAG | 0.859 | 0.875 | 0.667 |

**Δ ACME vs RAG (KU):** +0.056  
**Δ ACME vs MemGPT (KU):** +0.028

Prior graph-only ACME run (job `d842211c`, same subset): KU **0.139**, overall 0.179.

Reproduce: `bash scripts/run_longmemeval_prod.sh`

---

## LongMemEval — remaining types (422 Q)

| Field | Value |
|-------|-------|
| Job ID | `26e288da-d5dc-47a9-a399-46170b43894b` |
| Completed | 2026-06-25 (poll) |
| Duration | 18 643 s (~5.2 h) |
| Types | single-session-*, multi-session, temporal-reasoning |
| Failures | none |

| System | Overall | Multi-session | Temporal | SS-user | SS-asst | SS-pref |
|--------|---------|---------------|----------|---------|---------|---------|
| **ACME** | **0.787** | **0.760** | **0.709** | **1.000** | **1.000** | **0.567** |
| RAG | 0.761 | 0.810 | 0.622 | 1.000 | 0.964 | 0.400 |
| MemGPT | 0.763 | 0.769 | 0.630 | 1.000 | 0.982 | 0.533 |

---

## LongMemEval — full oracle 500 Q (v5 hybrid, canonical)

| Field | Value |
|-------|-------|
| Job ID | `45623ca0-1279-4d99-8e40-52ce84b7e753` |
| Completed | 2026-06-26 (poll) |
| Duration | ~22 400 s (~6.2 h) |
| Image | `acme-api:longmemeval-v5-hybrid` |
| Failures | none |

| System | Overall | KU | Multi-session | Temporal | SS-user | SS-asst | SS-pref | Abstention |
|--------|---------|-----|---------------|----------|---------|---------|---------|------------|
| **ACME** | **0.876** | **0.944** | **0.793** | **0.803** | **1.000** | **1.000** | **0.900** | **0.833** |
| MemGPT | 0.786 | 0.861 | 0.793 | 0.630 | 1.000 | 0.982 | 0.600 | 0.600 |
| RAG | 0.776 | 0.875 | 0.793 | 0.622 | 1.000 | 0.964 | 0.467 | 0.600 |

**Δ ACME vs RAG (500 Q):** +0.100 overall

Reproduce: `LONGMEMEVAL_TYPES=all bash scripts/run_longmemeval_prod.sh`

**v4 → v5 ACME:** overall +2.8 pt · temporal +9.4 pt · abstention +10 pt

Summary: `benchmark-results/longmemeval-v5-full-500q.json`

---

## LongMemEval — combined oracle v4 (superseded hybrid)

| System | Overall |
|--------|---------|
| ACME | 0.848 |
| RAG | 0.780 |

Summary: `benchmark-results/longmemeval-v4-combined.json`

### v4 routing run (241 Q) — job `c81eaa91`

| System | Overall | Multi-session | Preference | KU | Abstention (in run) |
|--------|---------|---------------|------------|-----|---------------------|
| **ACME** | **0.863** | **0.793** | **0.933** | **0.944** | **0.889** |
| RAG | 0.772 | 0.793 | 0.433 | 0.889 | 0.722 |
| MemGPT | 0.776 | 0.802 | 0.533 | 0.875 | 0.611 |

Duration ~213 min · image `acme-api:longmemeval-v4-routing`

**ACME v3 → v4 deltas:** abstention +35.6 pt · preference +36.7 pt · multi-session +3.3 pt · KU +1.4 pt

---

## LongMemEval — combined oracle v3 (superseded)

| System | Overall |
|--------|---------|
| ACME | 0.804 |
| RAG | 0.776 |

Summary: `benchmark-results/longmemeval-v3-combined.json`

---

### Ablation sweep (v3.1, GPT-4.1, 24 June 2026)

| Configuration | Overall | Retention | Groundedness | Feedback | Belief |
|---------------|---------|-----------|--------------|----------|--------|
| Full ACME (compare v3) | 0.925 | 1.000 | 1.000 | 1.000 | 0.700 |
| No contrarian | 0.923 | 1.000 | 0.993 | 1.000 | 0.700 |
| No belief sync | 0.731 | 0.996 | 1.000 | 0.929 | 0.000 |
| No vector | 0.923 | 0.993 | 1.000 | 1.000 | 0.700 |

Reproduce: `./azure/configure-premium-ingress.sh && ./scripts/run_ablation_prod.sh`
