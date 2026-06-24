# ACME: Adaptive Cognitive Memory Engine
## Externalizing Belief, Memory, and Learning from LLM Weights

**arXiv preprint draft v1.1 — June 2026**

**Author:** Mohamed Kamil Bourouiba  
**Code:** https://github.com/KamilBourouiba/ACME (tag `v0.1.1-arxiv`)  
**Project site:** https://kamilbourouiba.github.io/ACME/  
**Data:** Production benchmark exports via `GET /api/v1/benchmark/export` (persisted in Postgres `benchmark_runs`)

---

### Abstract

Large language models lack durable episodic memory, explicit belief states, structured forgetting, and mechanisms to learn from failure [1,2]. We present **ACME** (Adaptive Cognitive Memory Engine), an external cognitive substrate that treats the LLM as a language processor while delegating persistence, confidence tracking, contradiction handling, and self-correction to specialized engines. ACME operationalizes: *when does a collection of experiences deserve to become a belief?* We contribute (1) a promotion/demotion lifecycle with Cognitive Reliability Score (CRS), inspired by evidence-accumulation models in cognitive architecture [3,4]; (2) hybrid graph + pgvector retrieval [5,6] with contrarian verification [7,8]; (3) **MemoryBench v3** — thirteen sandbox-isolated scenarios with RAG [9], MemGPT [10], and LangGraph-style [11] baselines scored by an LLM judge [12,13]. On Azure OpenAI GPT-4.1 with `text-embedding-3-small` (256D) and Postgres Flexible + pgvector, ACME achieves overall **0.925** vs **0.487** for vector-RAG (MemoryBench v3, 24 June 2026 production run, job `3b31e5e3`), with full feedback and belief-quality metrics unavailable to baselines. Model-sensitivity runs on GPT-4.1-mini and GPT-5.4 preserve a **+0.39–0.44** margin over RAG.

---

### 1. Introduction

Retrieval-augmented generation (RAG) [9] augments LLMs with document search but does not maintain explicit epistemic states, handle contradictory evidence, or learn from prediction failures. Dense and hybrid retrievers [14,15] improve recall yet remain stateless: they neither promote stable beliefs nor demote refuted hypotheses. Agent memory frameworks — MemGPT [10], generative agents [16], and LangGraph-style orchestration [11] — extend context windows via paging or state graphs but lack auditable belief lifecycles and structured feedback loops comparable to cognitive architectures [3,17].

Episodic and semantic memory have long been distinguished in psychology and AI [18,19]. Recent work on long-term conversational memory (MemGPT, memory streams [16], Zep [20]) focuses on *what to store and retrieve*, not *when accumulated evidence warrants belief*. ACME closes this gap with an explicit promotion pipeline (Observation → Inference → Hypothesis → Belief) and symmetric demotion under contradiction — aligning with truth-maintenance and belief-revision traditions [21,22].

ACME externalizes cognition into specialized engines:

- **Episodic store** (PostgreSQL + pgvector [23]) and **semantic graph** (Neo4j [24], tenant-scoped)
- **Belief engine** — observation → hypothesis → belief → challenged → deprecated → archived
- **Contrarian verification** on high-confidence answers [7,8]
- **Compression, forgetting, and autonomous learning** with prediction validation [25,26]
- **MemoryBench v3** for reproducible evaluation with CI gates

---

### 2. Related Work

**Retrieval-augmented generation.** Lewis et al. [9] established the retrieve-then-generate paradigm for knowledge-intensive tasks. Subsequent systems add re-ranking [14], query rewriting [27], and self-critique — Self-RAG [28] and Corrective RAG [29] route or revise retrieval based on generation quality. ACME differs by persisting structured beliefs and failure traces outside the LLM, not only refining a single-turn retrieval pass.

**Graph-augmented memory.** Knowledge-graph RAG [30,31] and GraphRAG [32] extract communities and summaries from document graphs. ACME maintains a *live* typed graph (entities, causal edges, tenant scope) updated on every experience, coupled with vector recall over episodic embeddings — hybrid retrieval akin to [5,6] but with belief-weighted context assembly.

**Agent memory systems.** MemGPT [10] virtualizes context via OS-inspired paging; generative agents [16] use memory streams and reflection; LangGraph [11] composes stateful agent workflows. These systems improve *capacity* and *session continuity*; ACME adds CRS-governed belief promotion, contradiction logging, and prediction-outcome loops absent from reference baselines in our evaluation.

**Learning from feedback.** Reflexion [33] and ExpeL [34] use verbal reinforcement from trial outcomes; Constitutional AI [35] shapes behavior via principles. ACME's feedback engine ties outcome signals to specific graph-backed beliefs, adjusting confidence and status (e.g., Challenged → Deprecated) rather than only updating prompt-level reflections.

**Cognitive architectures.** ACT-R [3] and SOAR [17] model declarative memory, production rules, and learning from impasse. ACME is not a full cognitive architecture but borrows the separation of *fast reasoning* (LLM) from *slow accumulative memory* (Postgres, Neo4j, belief records) — similar in spirit to dual-process accounts [4] and complementary learning systems [36].

**Evaluation of memory systems.** Benchmarks such as LongMemEval [37], LoCoMo [38], and MemoryBank [39] stress long-horizon recall. MemoryBench v3 additionally scores feedback correction, belief quality, hallucination resistance under adversarial queries, and per-scenario sandbox isolation — metrics orthogonal to pure retention [12,13].

---

### 3. System Design

**Ingestion:** LLM extraction [40] plus deterministic normalization → Neo4j entities/relations + episodic embeddings [23].

**Query:** Hybrid retrieval (graph neighborhood [24,30] + pgvector cosine [5]) → LLM reasoning → optional contrarian pass [7,8] when confidence ≥ 0.8.

**Feedback:** Outcome signals update beliefs [21], log failures [33], trigger consolidation (scheduled consolidation, 6 h).

**CRS (Cognitive Reliability Score)** = 40% prediction success + 20% temporal stability + 20% contradiction resistance + 20% source diversity — a composite reliability index analogous to calibrated confidence under heterogeneous evidence [41,42].

**Causal edge types:** `observed_with`, `precedes`, `correlates`, `causes`, `disproves` — distinguishing correlation from causation per Pearlian and epistemic traditions [43,44].

**Multi-tenancy:** Postgres rows and Neo4j nodes keyed by `tenant_id` (header `X-Tenant-ID`).

**Ablation toggles:** `ABLATION_DISABLE_CONTRARIAN`, `ABLATION_DISABLE_BELIEF_SYNC`, `ABLATION_DISABLE_VECTOR` (see Section 6).

---

### 4. MemoryBench v3

Four metrics, LLM-as-judge [12,13] (semantic; keyword overlap reported separately):

| Metric | Description |
|--------|-------------|
| Retention | Concept coverage (synonyms accepted) |
| Groundedness | Answer supported by ingested episodes [45,46] |
| Feedback correction | Belief adjustment after contradictions [21,33] |
| Belief quality | Mean CRS across tracked beliefs |

**Overall** = average of all four. Baselines score 0 on feedback/belief (N/A), capping baseline overall near 0.48–0.49.

**Thirteen scenarios:** retention, contradiction, multi-source conflict, error injection, long-term retention, hallucination resistance, feedback adjustment, adversarial noise, long-horizon noise, tenant isolation, healthcare domain transfer, multi-session recall, prediction-outcome loop.

**Isolation:** Each scenario deletes prior benchmark-tagged Postgres rows and Neo4j subgraph before run (`acme/evaluation/sandbox.py`) — preventing cross-scenario contamination noted as a failure mode in long-horizon evals [37,38].

**Baselines:** Minimal reproducible implementations aligned with Lewis et al. [9] (RAG), Packer et al. [10] (MemGPT), and LangGraph-style state graphs [11] — see `docs/BASELINES.md`.

---

### 5. Experimental Setup

| Component | Configuration |
|-----------|---------------|
| LLM | Azure OpenAI GPT-4.1 [47] |
| Embeddings | `text-embedding-3-small`, 256 dimensions [48] |
| Database | Azure Postgres Flexible (pgvector [23]), francecentral |
| Graph | Neo4j 5.x on Azure Container Apps [24] |
| Judge | Same deployment as extractor/reasoner (`evaluate_answer_quality`) [12] |
| Reproducibility | `POST /api/v1/benchmark/memorybench`, `POST /api/v1/benchmark/compare/async` |

**Model-sensitivity runs** additionally use GPT-4.1-mini and GPT-5.4 (same endpoint family; GPT-5.4 requires `max_completion_tokens` API parameter).

---

### 6. Results (Azure production, 24 June 2026, 13 scenarios, isolated)

**Run metadata:** API revision `acme-api--membenchfix`; compare job `3b31e5e3-72b1-4ce3-b6c2-848cf94e4128`; duration 725 s; zero scenario failures.

| System | Retention | Groundedness | Feedback | Belief Q. | Overall |
|--------|-----------|--------------|----------|-----------|---------|
| **ACME** | **1.000** | **1.000** | **1.000** | **0.700** | **0.925** |
| RAG baseline | 0.969 | 0.977 | N/A | N/A | 0.487 |
| MemGPT baseline | 0.977 | 0.969 | N/A | N/A | 0.487 |
| LangGraph baseline | 0.900 | 0.977 | N/A | N/A | 0.469 |

*Baselines exclude feedback/belief in overall (not applicable). Scores rounded to three decimals from persisted `benchmark_runs` export.*

**Key finding:** ACME gains **+0.44** overall vs RAG primarily from feedback correction and belief quality — dimensions absent from all baselines [10,11]. Retention and groundedness are competitive across systems (all ≥ 0.90 on applicable metrics), consistent with strong vector and graph-augmented recall [9,32].

**Model sensitivity (GPT-4.1-mini):** Job `107d02c0`, 639 s. ACME retains **+0.39** overall vs RAG (0.858 vs 0.473). Feedback stays at 1.000 and belief at 0.700 — cognitive layers compensate when the base model is weaker [4,36].

| System | Retention | Groundedness | Feedback | Belief Q. | Overall |
|--------|-----------|--------------|----------|-----------|---------|
| **ACME** | **0.892** | **0.838** | **1.000** | **0.700** | **0.858** |
| RAG baseline | 0.908 | 0.985 | N/A | N/A | 0.473 |
| MemGPT baseline | 0.915 | 1.000 | N/A | N/A | 0.479 |
| LangGraph baseline | 0.854 | 0.862 | N/A | N/A | 0.429 |

**Model sensitivity (GPT-5.4):** Job `eb68f028`, 620 s. ACME **0.873** vs RAG **0.474** (**+0.40**).

| System | Retention | Groundedness | Feedback | Belief Q. | Overall |
|--------|-----------|--------------|----------|-----------|---------|
| **ACME** | **0.952** | **0.839** | **1.000** | **0.701** | **0.873** |
| RAG baseline | 0.964 | 0.931 | N/A | N/A | 0.474 |
| MemGPT baseline | 0.975 | 0.939 | N/A | N/A | 0.478 |
| LangGraph baseline | 0.973 | 0.950 | N/A | N/A | 0.481 |

Belief quality remains **~0.70** across all three LLM tiers — suggesting the external belief substrate [3,21] is comparatively stable while retention/groundedness track model capability [12].

**Ablation (design):** Disabling contrarian checks, belief sync, or vector retrieval is supported via environment flags; unit gates verify toggles (`scripts/run_ablation_gate.py`). Full ablation sweeps on live LLM runs are left to future work.

---

### 7. Limitations

- LLM judge and extractor introduce variance [12,13]; we report sandbox-isolated runs with persisted `benchmark_runs`.
- Scenarios emphasize SaaS churn/latency plus one healthcare transfer set; broader domains and multilingual evals needed [37,38].
- Baselines are reference implementations, not full upstream MemGPT/LangGraph codebases [10,11].
- Production API requires API key for benchmark endpoints.
- CRS weights are hand-tuned; calibration against human epistemic judgments [41] is future work.

---

### 8. Conclusion

ACME shows that externalizing belief and learning from LLM weights yields stronger cognitive memory than vector RAG or lightweight agent-memory baselines on MemoryBench v3, especially for feedback-driven correction and auditable belief quality. The consistent **+0.39–0.44** margin over RAG across GPT-4.1, GPT-4.1-mini, and GPT-5.4 supports the hypothesis that explicit belief lifecycle management [21,22] complements — rather than replaces — advances in base model capability [1,47].

---

### References

1. Bommasani, R. et al. On the Opportunities and Risks of Foundation Models. *arXiv:2108.07258*, 2021.
2. McKenna, B. et al. Towards Reliable Generation: Rethinking Faithfulness and Hallucination in LLMs. *Findings of ACL*, 2024.
3. Anderson, J. R., Bothell, D., Byrne, M. D., Douglass, S., Lebiere, C., & Qin, Y. An Integrated Theory of the Mind. *Psychological Review*, 111(4), 1036–1060, 2004.
4. Evans, J. S. B. T. & Stanovich, K. E. Dual-Process Theories of Higher Cognition. *Perspectives on Psychological Science*, 8(3), 223–241, 2013.
5. Gao, L. et al. Retrieval-Augmented Generation for Large Language Models: A Survey. *arXiv:2312.10997*, 2023.
6. Wang, X. et al. Searching for Best Practices in Retrieval-Augmented Generation. *arXiv:2407.01219*, 2024.
7. Madaan, A. et al. Self-Refine: Iterative Refinement with Self-Feedback. *NeurIPS*, 2023.
8. Saunders, W. et al. Self-Critiquing Models for Assisting Human Evaluators. *arXiv:2206.05802*, 2022.
9. Lewis, P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS*, 2020.
10. Packer, C. et al. MemGPT: Towards LLMs as Operating Systems. *arXiv:2310.08560*, 2023.
11. LangChain. LangGraph: Building Stateful, Multi-Actor Applications with LLMs. Documentation, 2024. https://langchain-ai.github.io/langgraph/
12. Zheng, L. et al. Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. *NeurIPS*, 2023.
13. Liu, Y. et al. G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment. *EMNLP*, 2023.
14. Karpukhin, V. et al. Dense Passage Retrieval for Open-Domain Question Answering. *EMNLP*, 2020.
15. Khattab, O. & Zaharia, M. ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction. *SIGIR*, 2020.
16. Park, J. S. et al. Generative Agents: Interactive Simulacra of Human Behavior. *UIST*, 2023.
17. Laird, J. E. The SOAR Cognitive Architecture. *MIT Press*, 2012.
18. Tulving, E. Episodic and Semantic Memory. In *Organization of Memory*, 1972.
19. Schacter, D. L. & Tulving, E. Memory Systems. *MIT Press*, 1994.
20. Rasmussen, D. et al. Zep: A Temporal Knowledge Graph Architecture for Agent Memory. *arXiv:2501.13956*, 2025.
21. Doyle, J. A Truth Maintenance System. *Artificial Intelligence*, 12(3), 231–272, 1979.
22. Gardenfors, P. *Knowledge in Flux: Modeling the Dynamics of Epistemic States*. MIT Press, 1988.
23. pgvector. Open-source vector similarity search for PostgreSQL. https://github.com/pgvector/pgvector
24. Neo4j, Inc. Neo4j Graph Database. https://neo4j.com/
25. Parisi, G. I. et al. Continual Lifelong Learning with Neural Networks: A Review. *Neural Networks*, 113, 54–71, 2019.
26. Kemper, N. & Jankowski, S. Forgetting in Deep Learning — A Survey. *arXiv:2307.09218*, 2023.
27. Ma, X. et al. Query Rewriting for Retrieval-Augmented Large Language Models. *EMNLP*, 2023.
28. Asai, A. et al. Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection. *ICLR*, 2024.
29. Yan, S. et al. Corrective Retrieval Augmented Generation. *arXiv:2401.15884*, 2024.
30. Edge, D. et al. From Local to Global: A Graph RAG Approach to Query-Focused Summarization. *arXiv:2404.16130*, 2024 (Microsoft GraphRAG).
31. Wang, M. et al. Knowledge Graph Prompting for Multi-Document Question Answering. *EMNLP*, 2023.
32. Edge, D. et al. GraphRAG: Unlocking LLM Discovery on Narrative Private Data. Microsoft Research, 2024.
33. Shinn, N. et al. Reflexion: Language Agents with Verbal Reinforcement Learning. *NeurIPS*, 2023.
34. Zhao, A. et al. ExpeL: LLM Agents Are Experiential Learners. *AAAI*, 2024.
35. Bai, Y. et al. Constitutional AI: Harmlessness from AI Feedback. *arXiv:2212.08073*, 2022.
36. McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. Why There Are Complementary Learning Systems in the Hippocampus and Neocortex. *Psychological Review*, 102(3), 419–457, 1995.
37. Wu, Y. et al. LongMemEval: Benchmarking Long-Term Memory in LLMs. *arXiv:2410.10813*, 2024.
38. Maharana, D. et al. Evaluating Very Long-Term Conversational Memory of LLM Agents (LoCoMo). *ACL*, 2024.
39. Zhong, W. et al. MemoryBank: Enhancing Large Language Models with Long-Term Memory. *AAAI*, 2024.
40. Wang, X. et al. Text2KG: A Survey on Knowledge Graph Construction from Text. *arXiv:2404.09425*, 2024.
41. Guo, C. et al. On Calibration of Modern Neural Networks. *ICML*, 2017.
42. Kadavath, S. et al. Language Models (Mostly) Know What They Know. *arXiv:2207.05221*, 2022.
43. Pearl, J. *Causality: Models, Reasoning, and Inference*. Cambridge University Press, 2009.
44. Halpern, J. Y. *Actual Causality*. MIT Press, 2016.
45. Ji, Z. et al. Survey of Hallucination in Natural Language Generation. *ACM Computing Surveys*, 55(12), 2023.
46. Min, S. et al. FactScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation. *EMNLP*, 2023.
47. OpenAI. GPT-4.1 Model Card and System Documentation, 2025.
48. Neelakantan, A. et al. Text and Code Embeddings by Contrastive Pre-Training. *arXiv:2201.10005*, 2022.
49. Kamil Bourouiba. ACME: Adaptive Cognitive Memory Engine (code and benchmarks). https://github.com/KamilBourouiba/ACME, 2026.

---

### Appendix A — Reproduction

```bash
git clone https://github.com/KamilBourouiba/ACME.git && cd ACME
pip install -e ".[dev]"
pytest tests/test_benchmark_gate.py tests/test_memorybench.py -q
# Production (requires API key):
./azure/configure-premium-ingress.sh
./scripts/run_prod_benchmark.sh
./scripts/run_model_benchmark.sh gpt-4.1-mini   # optional model sweep
```

---

### Appendix B — Data Availability

Benchmark payloads stored in PostgreSQL table `benchmark_runs` (columns: `overall_score`, `retention_score`, `belief_quality_score`, `payload JSONB`, `created_at`). Export via `GET /api/v1/benchmark/export`. Full run tables: `docs/BENCHMARK_RESULTS.md` [49].
