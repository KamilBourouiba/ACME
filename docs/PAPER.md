---
title: "ACME: Adaptive Cognitive Memory Engine"
subtitle: "Externalizing Belief, Memory, and Learning from LLM Weights"
abstract: |
  Large language models lack durable episodic memory, explicit belief states, structured forgetting, and mechanisms to learn from failure [1,2]. Recent systems report that agents cannot epistemically separate observation from belief [50] and that intrinsic *epistemic agency* — including belief updating — remains weak in base models [51]. We present **ACME** (Adaptive Cognitive Memory Engine), an external cognitive substrate that treats the LLM as a language processor while delegating persistence, confidence tracking, contradiction handling, and self-correction to specialized engines. ACME operationalizes: *when does a collection of experiences deserve to become a belief?* We contribute (1) a CRS-governed belief lifecycle inspired by cognitive architecture [3,4] and truth-maintenance systems [21,54]; (2) hybrid graph + pgvector retrieval [5,6] with contrarian verification [7,8]; (3) **MemoryBench v3.1** — fourteen sandbox-isolated scenarios with RAG [9], MemGPT [10], and LangGraph-style [11] baselines scored by an LLM judge [12,13]. On Azure OpenAI GPT-4.1, ACME achieves overall **0.925** vs **0.487** for vector-RAG (job `3b31e5e3`), with feedback and belief-quality metrics unavailable to baselines. Model-sensitivity runs on GPT-4.1-mini and GPT-5.4 preserve a **+0.39–0.44** margin over RAG. Production ablations show belief sync is essential (−0.19 overall when disabled).
---

## Introduction

Retrieval-augmented generation (RAG) [9] augments LLMs with document search but does not maintain explicit epistemic states, handle contradictory evidence, or learn from prediction failures. LongMemEval [37] shows commercial assistants and long-context LLMs suffer **30–60%** accuracy drops on sustained interactive memory versus oracle evidence — retrieval alone is insufficient. Hindsight [50] argues current agent memory cannot distinguish *what was observed* from *what is believed*, nor maintain preference-consistent reasoning across sessions. Reflection-Bench [51] identifies **belief updating** and meta-reflection as core yet underdeveloped dimensions of epistemic agency in LLMs.

Dense and hybrid retrievers [14,15] improve recall yet remain stateless: they neither promote stable beliefs nor demote refuted hypotheses. Agent memory frameworks — MemGPT [10], generative agents [16], Zep [20], and LangGraph-style orchestration [11] — extend context windows via paging, temporal graphs, or state graphs but lack auditable belief lifecycles and structured feedback loops comparable to cognitive architectures [3,17].

Episodic and semantic memory have long been distinguished in psychology and AI [18,19]. Recent work on long-term conversational memory (MemGPT, memory streams [16], Zep [20]) focuses on *what to store and retrieve*, not *when accumulated evidence warrants belief*. ACME closes this gap with an explicit promotion pipeline (Observation -> Inference -> Hypothesis -> Belief) and symmetric demotion under contradiction — aligning with truth-maintenance and belief-revision traditions [21,22].

\begin{contributions}
\begin{enumerate}
\item A CRS-governed belief lifecycle with promotion and demotion under contradiction.
\item A hybrid graph + vector retrieval substrate (PostgreSQL/pgvector + Neo4j).
\item Contrarian verification for high-confidence answers.
\item MemoryBench v3.1 with scored belief and feedback metrics.
\item Production benchmark evidence across GPT-4.1, GPT-4.1-mini, and GPT-5.4.
\end{enumerate}
\end{contributions}

**Thesis.** RAG optimizes recall; ACME optimizes epistemic state---when experiences become beliefs, how contradictions demote them, and how outcomes close the prediction loop. Our claim is not universal SOTA on every long-context benchmark [37,38], but the first deployed system with sandbox-isolated evaluation of **feedback correction** and **belief quality (CRS)** against RAG/MemGPT/LangGraph under reproducible production runs [49].

## Related Work

**Retrieval-augmented generation.** Lewis et al. [9] established the retrieve-then-generate paradigm for knowledge-intensive tasks. Subsequent systems add re-ranking [14], query rewriting [27], and self-critique — Self-RAG [28] and Corrective RAG [29] route or revise retrieval based on generation quality. ACME differs by persisting structured beliefs and failure traces outside the LLM, not only refining a single-turn retrieval pass.

**Graph-augmented memory.** Knowledge-graph RAG [30,31] and GraphRAG [32] extract communities and summaries from document graphs. ACME maintains a *live* typed graph (entities, causal edges, tenant scope) updated on every experience, coupled with vector recall over episodic embeddings — hybrid retrieval akin to [5,6] but with belief-weighted context assembly.

**Agent memory systems.** MemGPT [10] virtualizes context via OS-inspired paging; generative agents [16] use memory streams and reflection; LangGraph [11] composes stateful agent workflows. These systems improve *capacity* and *session continuity*; ACME adds CRS-governed belief promotion, contradiction logging, and prediction-outcome loops absent from reference baselines in our evaluation.

**Learning from feedback.** Reflexion [33] and ExpeL [34] use verbal reinforcement from trial outcomes; Constitutional AI [35] shapes behavior via principles. ACME's feedback engine ties outcome signals to specific graph-backed beliefs, adjusting confidence and status (e.g., Challenged -> Deprecated) rather than only updating prompt-level reflections.

**Cognitive architectures.** ACT-R [3] and SOAR [17] model declarative memory, production rules, and learning from impasse. ACME is not a full cognitive architecture but borrows the separation of *fast reasoning* (LLM) from *slow accumulative memory* (Postgres, Neo4j, belief records) — similar in spirit to dual-process accounts [4] and complementary learning systems [36].

**Evaluation of memory systems.** Benchmarks such as LongMemEval [37], LoCoMo [38], MemoryBank [39], MemoryAgentBench [52], and MemBench [53] stress long-horizon recall, test-time learning, or reflective memory. Reflection-Bench [51] evaluates belief updating as one of seven epistemic dimensions. None jointly measure sandbox-isolated **feedback correction**, **CRS belief quality**, and **contrarian groundedness** in a production-deployable API. MemoryBench v3.1 fills this gap (Table 1).

**Belief-first and epistemic agent memory (concurrent work).** TruthKeeper [54] applies dependency-aware truth maintenance to LLM memory. MnemeBrain [55] stores beliefs with Belnap four-valued logic and AGM-style revision. NeuSymMS [56] couples neural extraction with symbolic TMS via rule engines. Graph-native cognitive memory architectures [57] formalize versioned belief revision for auditability. Hindsight [50] achieves strong LongMemEval/LoCoMo scores via retain-recall-reflect tiers but does not expose CRS-governed promotion thresholds or prediction-outcome loops. **ACME** differentiates by (i) integrated seven-engine cognitive loop with production deployment, (ii) MemoryBench v3.1 scoring belief/feedback dimensions absent from retrieval-centric baselines, and (iii) persisted `benchmark_runs` for third-party reproduction.

## System Design

\acmeFigureLoop

**Ingestion:** LLM extraction [40] plus deterministic normalization -> Neo4j entities/relations + episodic embeddings [23].

**Query:** Hybrid retrieval (graph neighborhood [24,30] + pgvector cosine [5]) -> LLM reasoning -> optional contrarian pass [7,8] when confidence >= 0.8.

**Feedback:** Outcome signals update beliefs [21], log failures [33], trigger consolidation (scheduled consolidation, 6 h).

\acmeFigureBelief

**CRS (Cognitive Reliability Score)** = 40% prediction success + 20% temporal stability + 20% contradiction resistance + 20% source diversity — a composite reliability index analogous to calibrated confidence under heterogeneous evidence [41,42].

**Causal edge types:** `observed_with`, `precedes`, `correlates`, `causes`, `disproves` — distinguishing correlation from causation per Pearlian and epistemic traditions [43,44].

**Multi-tenancy:** Postgres rows and Neo4j nodes keyed by `tenant_id` (header `X-Tenant-ID`).

**Ablation toggles:** `ABLATION_DISABLE_CONTRARIAN`, `ABLATION_DISABLE_BELIEF_SYNC`, `ABLATION_DISABLE_VECTOR` (see Results).

## MemoryBench v3.1

Four metrics, LLM-as-judge [12,13] (semantic; keyword overlap reported separately):

\acmeTableMetrics

**Overall** = average of all four. Baselines score 0 on feedback/belief (N/A), capping baseline overall near 0.48–0.49.

**Fourteen scenarios:** retention, contradiction, multi-source conflict, error injection, **knowledge update** (LongMemEval KU [37]), long-term retention, hallucination resistance, feedback adjustment, adversarial noise, long-horizon noise, tenant isolation, healthcare domain transfer, multi-session recall, prediction-outcome loop.

**Isolation:** Each scenario deletes prior benchmark-tagged Postgres rows and Neo4j subgraph before run (`acme/evaluation/sandbox.py`) — preventing cross-scenario contamination noted as a failure mode in long-horizon evals [37,38,51].

**Baselines:** Minimal reproducible implementations aligned with Lewis et al. [9] (RAG), Packer et al. [10] (MemGPT), and LangGraph-style state graphs [11] — see `docs/BASELINES.md`.

\acmeTablePositioningCapabilities

Primary reported results use the **13-scenario v3** suite (job `3b31e5e3`, pre-`knowledge_update`) for strict comparability; v3.1 adds the LongMemEval-aligned knowledge-update probe.

\acmeTablePositioningInfra

\begin{keyfinding}
\textbf{Key finding.} MemoryBench v3.1 is the only evaluated suite in our comparison that jointly scores \textbf{feedback correction}, \textbf{CRS belief quality}, and \textbf{contrarian groundedness} under per-scenario sandbox isolation with a production API.
\end{keyfinding}

## LongMemEval (industry benchmark)

To complement MemoryBench, we integrate the official **LongMemEval** oracle split [37] (500 questions, evidence sessions only). Chat histories are ingested via the same production orchestrator; answers are scored with the **official LongMemEval yes/no judge prompts** from the reference implementation.

\acmeTableLongMemEvalProtocol

\acmeTableLongMemEvalKU

**Protocol.** Each question resets sandbox state (`longmemeval` tag). Haystack sessions are serialized as multi-turn user/assistant transcripts and ingested as experiences. ACME uses a **transcript-first** answer path: sessions are ranked newest-first, the LLM reads full chat transcripts (with belief graph as secondary context), and knowledge-update items trigger belief demotion on superseded sources. RAG and MemGPT baselines answer from retrieved context; an independent LLM judge (same deployment family as MemoryBench) applies type-specific rubrics (`knowledge-update`, `temporal-reasoning`, `abstention`, etc.).

**Production run (June 2026):** job `705eb2ff`, API `acme-api:longmemeval-transcript`, 78 `knowledge-update` questions (72 core + 6 abstention probes), ~59 min, zero errors.

**Reproduction:**
```bash
bash scripts/download_longmemeval.sh
bash scripts/run_longmemeval_prod.sh   # Azure API
# or locally:
python scripts/run_longmemeval.py --types knowledge-update --systems acme,rag,memgpt
```

Results export to `benchmark-results/longmemeval-latest.json`. LongMemEval measures **QA accuracy over chat history**; MemoryBench measures **belief lifecycle and feedback** --- the two benchmarks are complementary and must not be merged into a single score.

\begin{keyfinding}
\textbf{Key finding.} On LongMemEval \texttt{knowledge-update} (oracle, GPT-4.1), ACME transcript-first reaches \textbf{93.1\%} KU accuracy vs.\ 87.5\% (RAG) and 90.3\% (MemGPT) --- closing the gap from graph-only retrieval (13.9\% KU in the prior run) while preserving MemoryBench belief/feedback advantages (Section 6).
\end{keyfinding}

## Experimental Setup

\acmeTableSetup

**Model-sensitivity runs** additionally use GPT-4.1-mini and GPT-5.4 (same endpoint family; GPT-5.4 requires `max_completion_tokens` API parameter).

\FloatBarrier

## Results

**Run metadata:** API revision `acme-api--membenchfix`; compare job\
`3b31e5e3-72b1-4ce3-b6c2-848cf94e4128`; duration 725 s; zero scenario failures.

\acmeResultSummary

\acmeTableMain

*Baselines exclude feedback/belief in overall (not applicable). Scores rounded to three decimals from persisted `benchmark_runs` export.*

\begin{keyfinding}
\textbf{Key finding.} ACME's advantage comes primarily from \textbf{feedback correction} and \textbf{belief quality}, rather than from raw retention alone. ACME gains \textbf{+0.44} overall vs RAG on GPT-4.1 while retention and groundedness remain competitive ($\geq 0.90$) across systems [9,32].
\end{keyfinding}

### Model sensitivity (GPT-4.1-mini)

Job `107d02c0`, 639 s. ACME retains **+0.39** overall vs RAG (0.858 vs 0.473). Feedback stays at 1.000 and belief at 0.700 — cognitive layers compensate when the base model is weaker [4,36].

\acmeTableMini

### Model sensitivity (GPT-5.4)

Job `eb68f028`, 620 s. ACME **0.873** vs RAG **0.474** (**+0.40**).

\acmeTableGptFiveFour

Belief quality remains **~0.70** across all three LLM tiers — suggesting the external belief substrate [3,21] is comparatively stable while retention/groundedness track model capability [12].

### Component ablations

We disable one cognitive layer at a time via environment flags (`scripts/run_ablation_prod.sh`). Table 2 reports ACME-only MemoryBench v3.1 scores (no baseline compare — 4x cost reduction per ablation).

\acmeTableAblations

*Full ACME row from 13-scenario compare (job `3b31e5e3`). Ablation rows from ACME-only runs on GPT-4.1 (24 June 2026, premium ingress, stamp `20260624213154`).*

\begin{keyfinding}
\textbf{Key finding.} Disabling belief sync collapses belief quality to \textbf{0.000} and overall score by \textbf{$-$0.19}, confirming the belief engine as the primary differentiator. Contrarian and vector ablations each reduce overall by only \textbf{$-$0.002}.
\end{keyfinding}

## Limitations

\begin{keyfinding}
\textbf{Key limitations.}
\begin{itemize}
\item LLM judge and extractor introduce variance [12,13]; we report sandbox-isolated runs with persisted \texttt{benchmark\_runs}.
\item Scenarios emphasize SaaS churn/latency plus one healthcare transfer set; broader domains and multilingual evals needed [37,38].
\item Baselines are reference implementations, not full upstream MemGPT/LangGraph codebases [10,11].
\item Production API requires API key for benchmark endpoints.
\item CRS weights are hand-tuned; calibration against human epistemic judgments [41] is future work.
\end{itemize}
\end{keyfinding}

## Conclusion

ACME shows that externalizing belief and learning from LLM weights yields stronger cognitive memory than vector RAG or lightweight agent-memory baselines on MemoryBench, especially for feedback-driven correction and auditable belief quality. The consistent **+0.39–0.44** margin over RAG across GPT-4.1, GPT-4.1-mini, and GPT-5.4 supports the hypothesis that explicit belief lifecycle management [21,22,54,55] complements — rather than replaces — advances in base model capability [1,47]. Concurrent belief-memory systems [50,54,56,57] validate the problem direction; ACME contributes reproducible production evidence that epistemic layers — not retrieval alone — drive the measured gap.

\acmeBackMatterBegin
\acmeReferencesBegin

## References

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
50. Latif, E. et al. Hindsight is 20/20: Building Agent Memory that Retains, Recalls, and Reflects. *arXiv:2512.12818*, 2025.
51. Chen, Y. et al. Reflection-Bench: Evaluating Epistemic Agency in Large Language Models. *arXiv:2410.16270*, 2024.
52. MemoryAgentBench authors. Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions. *arXiv:2507.05257*, 2025.
53. Ai, J. et al. MemBench: Towards More Comprehensive Evaluation on the Memory of LLM-based Agents. *arXiv:2506.21605*, 2025.
54. TruthKeeper authors. TruthKeeper: A Curated Memory Architecture for LLMs with Dependency-Aware Truth Maintenance. *arXiv preprint*, 2024.
55. MnemeBrain. Belief-State Memory for AI Agents. https://github.com/mnemebrain/mnemebrain-lite, 2025.
56. NeuSymMS authors. NeuSymMS: A Hybrid Neuro-Symbolic Memory System for LLM Agents. *arXiv:2605.17596*, 2026.
57. Graph-Native Cognitive Memory authors. Formal Belief Revision Semantics for Versioned Memory Architectures. *arXiv:2603.17244*, 2026.
58. Alchourron, C. E., Gardenfors, P., & Makinson, D. On the Logic of Theory Change: Partial Meet Contraction and Revision Functions. *Journal of Symbolic Logic*, 50(2), 510–530, 1985.

\acmeReferencesEnd

\begingroup\footnotesize

\section{Appendix A: Reproduction}
\label{appendix-a-reproduction}

\begin{tcolorbox}[
  enhanced,
  colback=bannerbg,
  colframe=keyborder!25,
  boxrule=0.35pt,
  arc=3pt,
  left=8pt, right=8pt, top=6pt, bottom=6pt
]
\begin{Verbatim}[fontsize=\scriptsize]
git clone https://github.com/KamilBourouiba/ACME.git && cd ACME
pip install -e ".[dev]"
pytest tests/test_benchmark_gate.py tests/test_memorybench.py -q
# Production (requires API key):
./azure/configure-premium-ingress.sh
./scripts/run_prod_benchmark.sh
./scripts/run_model_benchmark.sh gpt-4.1-mini   # optional model sweep
./scripts/run_ablation_prod.sh                # component ablations
\end{Verbatim}
\end{tcolorbox}

\section{Appendix B: Data Availability}
\label{appendix-b-data-availability}

Benchmark payloads are stored in PostgreSQL table \texttt{benchmark\_runs}
(columns: \texttt{overall\_score}, \texttt{retention\_score},
\texttt{belief\_quality\_score}, \texttt{payload JSONB}, \texttt{created\_at}).
Export via \texttt{GET /api/v1/benchmark/export}. Full run tables are documented
in \texttt{docs/BENCHMARK\_RESULTS.md}~[49].

\endgroup
