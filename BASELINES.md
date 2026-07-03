# MemoryBench baselines

ACME compares against three **reference implementations** aligned with published systems. These are reproducible runners that share the same LLM judge and scenarios as ACME — not full upstream Letta/MemGPT server deployments.

## RAG-like (`acme/evaluation/baseline_rag.py`)

- **Reference:** Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, NeurIPS 2020.
- **Implementation:** Embed all scenario episodes, cosine top-k retrieval, single LLM reasoning pass.
- **Missing vs ACME:** graph structure, beliefs, feedback loop, CRS, contrarian check.

## MemGPT-inspired (`acme/evaluation/baseline_memgpt.py`)

- **Reference:** Packer et al., *MemGPT: Towards LLMs as Operating Systems*, 2023.
- **Implementation (paper-faithful):** Fixed core window (last 3 episodes) + archival vector store. When core overflows, the **evicted episode is LLM-summarized** into archival memory before new content is added (MemGPT paging pattern).
- **Missing vs ACME:** persistence across sessions, belief lifecycle, structured forgetting, prediction validation.

## LangGraph-style (`acme/evaluation/baseline_langgraph.py`)

- **Reference:** LangGraph agent state graphs (LangChain documentation).
- **Implementation:** LLM extraction → append facts/edges to in-memory state; query uses last 40 facts.
- **Missing vs ACME:** durable episodic store, hybrid retrieval, belief engine, consolidation worker.

## LangGraph package runner (`acme/evaluation/baseline_langgraph_pkg.py`)

- **Optional:** `pip install langgraph langchain-core`
- **Implementation:** Official `StateGraph` compiled graph with the same fact accumulation semantics.
- **Use:** `scripts/run_local_fidelity_baselines.py` for supplementary local runs.

## Scoring fairness

| Dimension | ACME | Baselines |
|-----------|------|-----------|
| Retention | ✓ | ✓ |
| Groundedness | ✓ | ✓ |
| Feedback correction | ✓ | N/A (0 in overall index) |
| Belief quality (CRS) | ✓ | N/A (0 in overall index) |

Overall score is the unweighted mean of all four dimensions. Baselines receive **0** on feedback and belief in the capability index (shown as N/A in tables), so overall caps near ~0.49 even when retention and groundedness are strong.

## Analysis artifacts

| Artifact | Description |
|----------|-------------|
| `docs/benchmarks/job-3b31e5e3-export.json` | Archived per-scenario scores (primary run, bootstrap CIs) |
| `docs/benchmarks/compare-94005737.json` | Full compare payload (reproduction reference) |
| `docs/HUMAN_AUDIT_MEMORYBENCH.md` | 5-scenario author audit sample |
| `scripts/analyze_memorybench_export.py` | Bootstrap CIs + audit from live export |
| `scripts/generate_paper_ci_table.py` | LaTeX rows for paper CI table |

## Reproduce

```bash
# Prod compare (13-scenario v3 suite)
curl -X POST "$API/api/v1/benchmark/compare/async" -H "X-API-Key: $API_KEY"
curl "$API/api/v1/benchmark/compare/jobs/{job_id}" -H "X-API-Key: $API_KEY"

# Analysis + human audit pack
python scripts/analyze_memorybench_export.py

# Local paper-faithful baselines (requires AZURE_OPENAI_* in .env)
python scripts/run_local_fidelity_baselines.py
```

Letta (formerly MemGPT) server integration is out of scope for sandbox-isolated MemoryBench episodes but listed as future work.
