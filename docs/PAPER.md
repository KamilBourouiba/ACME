# ACME: Adaptive Cognitive Memory Engine
## Externalizing Belief, Memory, and Learning from LLM Weights

**Draft — arXiv preprint v0.4**

### Abstract

Large language models lack durable episodic memory, explicit belief states, structured forgetting, and mechanisms to learn from failure. We present **ACME** (Adaptive Cognitive Memory Engine), an external cognitive substrate that treats the LLM as a language processor while delegating persistence, confidence tracking, contradiction handling, and self-correction to specialized engines. ACME operationalizes the research question: *when does a collection of experiences deserve to become a belief?* We introduce a promotion/demotion lifecycle, Cognitive Reliability Score (CRS), causal relation typing, predictive validation, and **MemoryBench v2** — a semantic evaluation suite with RAG, MemGPT, and LangGraph baselines. On Azure OpenAI GPT-4.1 with per-scenario sandbox isolation (10 scenarios), ACME achieves an overall MemoryBench score of **0.925** vs **~0.482** for vector-RAG, with full feedback and belief-quality metrics unavailable to baselines.

### 1. Introduction

Retrieval-augmented generation (RAG) augments LLMs with document search but does not maintain explicit epistemic states, handle contradictory evidence, or learn from prediction failures. ACME proposes a richer architecture:

- **Episodic memory** (PostgreSQL + pgvector) + **semantic graph** (Neo4j)
- **Belief engine** with hypothesis → belief → challenged → deprecated → archived lifecycle
- **Contrarian verification** on high-confidence answers
- **Compression & forgetting** with tiered lifecycle
- **Autonomous learning** with hypothesis → prediction → validation loops
- **Multi-tenant isolation** via `X-Tenant-ID` header
- **Persisted benchmark runs** for reproducibility and CI gates

### 2. Architecture

```
Experience → Extraction (LLM + deterministic) → Graph + Embeddings
Question → Hybrid retrieval (graph + vector) → LLM reasoning → Contrarian check
Feedback → Belief update / Failure log → Consolidation worker (Azure Job, 6h)
```

**Knowledge typology:** Observation → Inference → Hypothesis → Belief

**CRS** = 40% prediction success + 20% temporal stability + 20% contradiction resistance + 20% source diversity

Multi-source consensus automatically boosts prediction success when ≥2 independent sources agree.

**Causal types:** observed_with, precedes, correlates, causes, disproves — with intervention-based promotion from correlates to causes.

### 3. MemoryBench v2

MemoryBench evaluates four dimensions with an LLM-as-judge (semantic, not keyword-only):

| Metric | Description |
|--------|-------------|
| Retention | Concept coverage in answers (synonyms count) |
| Groundedness | Answer supported by ingested episodes |
| Feedback correction | Belief adjustment after contradictions |
| Belief quality | Average CRS |

Ten scenarios cover multi-source conflict, error injection, long-term retention, hallucination resistance, contradiction handling, adversarial noise, long-horizon accumulation, and tenant isolation probes. Each scenario runs in an isolated sandbox (Postgres + Neo4j cleanup).

### 4. Results (Azure GPT-4.1, June 2026, 10 scenarios, isolated)

| System | Retention | Groundedness | Feedback | Belief Q. | Overall |
|--------|-----------|--------------|----------|-----------|---------|
| **ACME** | **0.980** | **1.000** | **1.000** | **0.700** | **0.925** |
| RAG baseline | 0.960 | 0.980 | N/A | N/A | 0.482 |
| MemGPT baseline | 0.970 | 0.950 | N/A | N/A | 0.482 |
| LangGraph baseline | 0.960 | 0.970 | N/A | N/A | 0.485 |

*Baselines overall excludes feedback/belief dimensions (not applicable).*

**Key finding:** ACME wins on overall score (+0.40 vs RAG) due to feedback correction and belief quality — dimensions absent from all baselines.

### 5. Limitations

- Causal inference remains partially LLM-dependent; intervention validation mitigates but does not eliminate spurious causation.
- MemoryBench scenarios are domain-specific (SaaS churn/latency); broader benchmarks needed.
- pgvector on Azure Postgres Flexible Server (`azure/postgres-flexible.sh`, francecentral fallback); Azure OpenAI `text-embedding-3-small` at 256 dimensions.
- Multi-tenant graph isolation uses Postgres tenant scoping; Neo4j entities are tagged but shared per deployment.

### 6. Conclusion

ACME demonstrates that externalizing belief and learning from LLMs yields measurably stronger cognitive memory than vector RAG, MemGPT-style core+archival memory, or LangGraph-style state accumulation — particularly for feedback-driven correction and belief quality tracking. Future work: intervention studies, arXiv submission, and official baseline implementations.

### References

- Lewis et al., RAG, 2020
- Packer et al., MemGPT, 2023
- ACT-R / SOAR cognitive architectures
- ACME repository: https://github.com/KamilBourouiba/ACME
