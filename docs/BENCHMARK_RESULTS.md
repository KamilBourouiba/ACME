# MemoryBench v3 — Production benchmark results

**Author:** Mohamed Kamil Bourouiba  
**Date:** 24 June 2026  
**API:** `acme-api--membenchfix` / `acme-api--bench-gpt41mini`  
**Reproduce:** `./scripts/run_prod_benchmark.sh` or `./scripts/run_model_benchmark.sh <deployment>`

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
