"""MemGPT-style baseline — core memory window + archival vector retrieval.

Reference: Packer et al., MemGPT (2023). See docs/BASELINES.md.
"""

from dataclasses import dataclass, field
from typing import Any

from acme.evaluation.memorybench import DEFAULT_SCENARIOS, MemoryBenchScenario, _avg, _overall
from acme.evaluation.scoring import keyword_retention_score
from acme.llm.base import BaseLLMClient
from acme.llm.embeddings import EmbeddingClient, cosine_similarity
from acme.schemas import MemoryBenchResult


@dataclass
class _MemGPTMemory:
    core: list[str] = field(default_factory=list)
    archival: list[tuple[str, list[float]]] = field(default_factory=list)


class MemGPTBaselineRunner:
    """Simplified MemGPT: fixed core window + archival vector store."""

    CORE_SIZE = 3

    def __init__(self, llm: BaseLLMClient, embedder: EmbeddingClient | None = None) -> None:
        self.llm = llm
        self.embedder = embedder or EmbeddingClient()
        self.memory = _MemGPTMemory()

    async def ingest(self, content: str) -> None:
        vec = await self.embedder.embed(content)
        self.memory.archival.append((content, vec))
        self.memory.core.append(content)
        if len(self.memory.core) > self.CORE_SIZE:
            self.memory.core.pop(0)

    async def query(self, question: str, top_k: int = 5) -> str:
        if not self.memory.archival:
            return "Insufficient memory to answer."
        q_vec = await self.embedder.embed(question)
        ranked = sorted(
            self.memory.archival,
            key=lambda item: cosine_similarity(q_vec, item[1]),
            reverse=True,
        )[:top_k]
        archival_context = "\n".join(f"- {text}" for text, _ in ranked)
        core_context = "\n".join(f"- {text}" for text in self.memory.core)
        memory_context = f"Core memory:\n{core_context}\n\nArchival memory:\n{archival_context}"
        result = await self.llm.reason(question=question, memory_context=memory_context)
        return str(result["answer"])

    async def _run_scenario(self, scenario: MemoryBenchScenario) -> dict[str, Any]:
        self.memory = _MemGPTMemory()
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
                "system": "memgpt_baseline",
                "scoring_method": "semantic_llm_judge",
                "scenarios_run": len(scenarios),
                "scenarios": results,
                "note": "MemGPT baseline has no belief/feedback layer",
            },
        )
