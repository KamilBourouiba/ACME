# MemoryBench baselines

ACME compares against three **reference implementations** aligned with published systems. These are deliberately minimal, reproducible runners that share the same LLM judge and scenarios as ACME — not full upstream codebases.

## RAG (`acme/evaluation/baseline_rag.py`)

- **Reference:** Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, 2020.
- **Implementation:** Embed all scenario episodes, cosine top-k retrieval, single LLM reasoning pass.
- **Missing vs ACME:** graph structure, beliefs, feedback loop, CRS, contrarian check.

## MemGPT (`acme/evaluation/baseline_memgpt.py`)

- **Reference:** Packer et al., *MemGPT: Towards LLMs as Operating Systems*, 2023.
- **Implementation:** Fixed core window (last 3 episodes) + archival vector store with cosine retrieval.
- **Missing vs ACME:** persistence across sessions, belief lifecycle, structured forgetting, prediction validation.

## LangGraph (`acme/evaluation/baseline_langgraph.py`)

- **Reference:** LangGraph-style agent state graphs (accumulated facts per session).
- **Implementation:** LLM extraction → append facts/edges to in-memory state; query uses last 40 facts.
- **Missing vs ACME:** durable episodic store, hybrid retrieval, belief engine, consolidation worker.

## Scoring fairness

| Dimension | ACME | Baselines |
|-----------|------|-----------|
| Retention | ✓ | ✓ |
| Groundedness | ✓ | ✓ |
| Feedback correction | ✓ | N/A (0.0) |
| Belief quality (CRS) | ✓ | N/A (0.0) |

Overall score averages all four dimensions. Baseline overall therefore caps at ~0.5 when retention and groundedness are strong.

## Reproduce

```bash
curl -X POST "$API/api/v1/benchmark/compare/async"
curl "$API/api/v1/benchmark/compare/jobs/{job_id}"
```

Official upstream MemGPT/LangGraph integrations are listed as future work in `docs/PAPER.md`.
