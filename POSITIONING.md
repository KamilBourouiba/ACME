# MemoryBench v3.1 — Benchmark positioning

How MemoryBench compares to contemporary memory and epistemic-agent evaluations (June 2026).

| Capability | LongMemEval | MemoryAgentBench | Reflection-Bench | MemBench | **MemoryBench v3.1** |
|------------|-------------|------------------|------------------|----------|----------------------|
| Long-horizon / multi-session | Yes | Yes | Partial | Yes | Yes |
| Knowledge update | Yes (KU) | Yes | Partial | Partial | Yes (`knowledge_update`) |
| Feedback / belief revision | No | Partial | Yes | Reflective memory | **Scored** |
| Hallucination / abstention | Yes | Partial | Partial | Partial | Yes |
| Per-scenario sandbox | No | Partial | Yes | Yes | **Postgres + Neo4j** |
| Contrarian / self-critique | No | No | Partial | No | **Yes** |
| Belief quality (CRS) | No | No | No | Partial | **Yes** |
| Production API + persisted runs | No | No | No | No | **Yes** |

## ACME thesis vs retrieval-centric evals

- **LongMemEval [ICLR 2025]** — proves long-context != robust memory (−30–60% vs oracle).
- **Hindsight [2025]** — agents conflate observation vs belief; ACME separates via belief engine.
- **Reflection-Bench [2024]** — belief updating is core epistemic agency; MemoryBench scores it.
- **TruthKeeper / MnemeBrain / NeuSymMS** — concurrent belief-memory; ACME adds prod benchmarks.

## References

- LongMemEval: https://arxiv.org/abs/2410.10813
- MemoryAgentBench: https://arxiv.org/abs/2507.05257
- Reflection-Bench: https://arxiv.org/abs/2410.16270
- MemBench: https://arxiv.org/html/2506.21605
- Hindsight: https://arxiv.org/abs/2512.12818

## LongMemEval adapter

ACME ships an official LongMemEval oracle adapter (`acme/evaluation/longmemeval.py`). See **`docs/LONGMEMEVAL.md`** for download, run, and interpretation.

```bash
bash scripts/download_longmemeval.sh
python scripts/run_longmemeval.py --types knowledge-update --systems acme,rag,memgpt
```
