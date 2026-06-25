"""RAG baseline — vector retrieval + LLM, no graph or beliefs.

Reference: Lewis et al., RAG (2020). See docs/BASELINES.md.
"""

from dataclasses import dataclass, field
from typing import Any

from acme.evaluation.memorybench import (
    DEFAULT_SCENARIOS,
    MemoryBenchScenario,
    _avg,
    _overall,
)
from acme.evaluation.scoring import keyword_retention_score
from acme.llm.base import BaseLLMClient
from acme.llm.embeddings import EmbeddingClient, cosine_similarity
from acme.schemas import MemoryBenchResult


@dataclass
class _RAGMemory:
    episodes: list[tuple[str, list[float]]] = field(default_factory=list)


class RAGBaselineRunner:
    """Minimal RAG: embed episodes, cosine retrieve, LLM reason — no ACME engines."""

    def __init__(self, llm: BaseLLMClient, embedder: EmbeddingClient | None = None) -> None:
        self.llm = llm
        self.embedder = embedder or EmbeddingClient()
        self.memory = _RAGMemory()

    async def ingest(self, content: str) -> None:
        vec = await self.embedder.embed(content)
        self.memory.episodes.append((content, vec))

    async def query(self, question: str, top_k: int = 5) -> str:
        if not self.memory.episodes:
            return "Insufficient memory to answer."
        q_vec = await self.embedder.embed(question)
        ranked = sorted(
            self.memory.episodes,
            key=lambda item: cosine_similarity(q_vec, item[1]),
            reverse=True,
        )[:top_k]
        context = "\n".join(f"- {text}" for text, _ in ranked)
        result = await self.llm.reason(question=question, memory_context=context)
        return str(result["answer"])

    async def _run_scenario(self, scenario: MemoryBenchScenario) -> dict[str, Any]:
        self.memory.episodes.clear()
        contents: list[str] = []
        for ep in scenario.episodes:
            await self.ingest(ep["content"])
            contents.append(ep["content"])

        answer = await self.query(scenario.query)
        concepts = scenario.expected_concepts or scenario.expected_keywords
        evaluation = await self.llm.evaluate_answer_quality(
            question=scenario.query,
            answer=answer,
            reference_concepts=concepts,
            source_episodes=contents,
        )
        return {
            "name": scenario.name,
            "retention_score": evaluation["retention_score"],
            "keyword_retention_score": keyword_retention_score(
                answer, scenario.expected_keywords or concepts
            ),
            "feedback_score": 0.0,
            "hallucination_score": evaluation["groundedness_score"],
            "belief_quality_score": 0.0,
            "answer_preview": answer[:200],
        }

    async def run(
        self,
        scenarios: list[MemoryBenchScenario] | None = None,
    ) -> MemoryBenchResult:
        scenarios = scenarios or DEFAULT_SCENARIOS
        results = [await self._run_scenario(s) for s in scenarios]
        retention = _avg([r["retention_score"] for r in results])
        hallucination = _avg([r["hallucination_score"] for r in results])
        return MemoryBenchResult(
            retention_score=retention,
            feedback_correction_score=0.0,
            hallucination_resistance_score=hallucination,
            belief_quality_score=0.0,
            overall_score=_overall(retention, 0.0, hallucination, 0.0),
            details={
                "system": "rag_baseline",
                "scoring_method": "semantic_llm_judge",
                "scenarios_run": len(scenarios),
                "scenarios": results,
                "note": "RAG has no belief/feedback layer — those metrics are N/A",
            },
        )
