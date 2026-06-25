"""Shared LLM client interface and helpers."""

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from acme.schemas import ExtractionResult, GraphEntity, GraphRelation, KnowledgeType


class BaseLLMClient(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def ping(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.2,
        timeout: float = 300.0,
        json_mode: bool = False,
    ) -> str:
        raise NotImplementedError

    async def extract_knowledge(self, content: str, action: str | None = None) -> ExtractionResult:
        system = (
            "You extract structured knowledge from experiences. "
            "Return ONLY valid JSON with keys: entities, relations, summary. "
            "Each entity: name, entity_type, knowledge_type (observation|inference|hypothesis). "
            "Each relation: source, target, relation_type, causal_type, knowledge_type, confidence (0-1). "
            "causal_type MUST be one of: observed_with, precedes, correlates, causes, disproves, related_to. "
            "Use 'causes' ONLY when causality is explicit. Default to correlates or observed_with. "
            "Distinguish observations (raw facts) from inferences (derived)."
        )
        prompt = f"""Extract entities and relations from this experience:

Action: {action or "none"}
Content: {content}

JSON:"""
        raw = await self.generate(prompt=prompt, system=system, temperature=0.1, timeout=300.0, json_mode=True)
        return self._to_extraction_result(self._parse_json(raw))

    async def reason(
        self,
        question: str,
        memory_context: str,
        extra_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        system = (
            "You are a reasoning engine with access to a memory graph. "
            "Use ONLY the provided memory context. If insufficient, say so. "
            "Return ONLY valid JSON: answer, reasoning, confidence (0-1), entities_used (list of strings)."
        )
        mode = (extra_context or {}).get("mode", "")
        if mode in ("longmemeval_transcript_first", "longmemeval_knowledge_update"):
            system += (
                " The memory context contains chat transcripts sorted newest-first. "
                "When sessions disagree, answer with the most recent fact. "
                "Give a direct concise answer (not 'insufficient' if the fact appears in any session)."
            )
        elif mode == "longmemeval_multi_session":
            system += (
                " Evidence may appear across multiple chat sessions. Read every session and "
                "aggregate facts (counts, totals, durations) before answering. "
                "Do not ignore older sessions when they contain relevant details."
            )
        elif mode == "longmemeval_temporal":
            system += (
                " Use session dates, the precomputed timeline, and the question date. "
                "Compute elapsed time step by step (subtract dates) before answering. "
                "State the interval explicitly (days, weeks, or months) in the final answer."
            )
        elif mode == "longmemeval_abstention":
            system += (
                " If the question names a person, place, object, sport, or topic that does NOT "
                "appear in the memory context, respond that the information provided is not enough "
                "or insufficient — do NOT answer using a similar but different entity or topic."
            )
        elif mode == "longmemeval_preference":
            system += (
                " The user has stated personal preferences in the transcripts. Your answer must "
                "explicitly reflect those preferences (cite them) rather than giving generic advice."
            )
        context_block = json.dumps(extra_context or {}, ensure_ascii=False)
        prompt = f"""Question: {question}

Memory context:
{memory_context}

Additional context:
{context_block}

JSON:"""
        raw = await self.generate(prompt=prompt, system=system, temperature=0.3, timeout=300.0, json_mode=True)
        parsed = self._parse_json(raw)
        return {
            "answer": self._coerce_text(parsed.get("answer"), "Insufficient memory to answer."),
            "reasoning": self._coerce_text(parsed.get("reasoning"), ""),
            "confidence": float(parsed.get("confidence", 0.3)),
            "entities_used": parsed.get("entities_used", []),
        }

    async def contrarian_check(self, claim: str, memory_context: str) -> str:
        system = (
            "You challenge conclusions with evidence-based counter-arguments. "
            "Be concise. Use the memory context. If no counter-evidence exists, say so."
        )
        prompt = f"""Claim: {claim}

Memory context:
{memory_context}

What evidence suggests the opposite view?"""
        return await self.generate(prompt=prompt, system=system, temperature=0.4, timeout=300.0)

    async def compress_episodes(
        self,
        episode_contents: list[str],
        cluster_key: str,
    ) -> dict[str, Any]:
        system = (
            "You discover patterns across similar experiences and produce abstractions. "
            "Return ONLY valid JSON with keys: "
            "abstraction (string), confidence (0-1), supporting_patterns (list), reasoning (string). "
            "Only abstract when a genuine repeated pattern exists. "
            "Do not over-generalize from few examples. "
            "Prefer cautious hypotheses over false rules."
        )
        episodes_block = "\n".join(f"- {content}" for content in episode_contents[:50])
        prompt = f"""Cluster key: {cluster_key}
Episode count: {len(episode_contents)}

Experiences:
{episodes_block}

Find the common pattern and compress into one abstraction.

JSON:"""
        raw = await self.generate(prompt=prompt, system=system, temperature=0.2, timeout=300.0, json_mode=True)
        parsed = self._parse_json(raw)
        return {
            "abstraction": parsed.get("abstraction"),
            "confidence": float(parsed.get("confidence", 0.5)),
            "supporting_patterns": parsed.get("supporting_patterns", []),
            "reasoning": parsed.get("reasoning", ""),
        }

    async def generate_hypotheses(self, memory_context: str) -> list[dict[str, Any]]:
        system = (
            "You are an autonomous learning engine. "
            "Analyze memory and propose testable hypotheses — not facts. "
            "Return ONLY valid JSON: {\"hypotheses\": [{"
            "\"statement\": str, \"rationale\": str, \"testable_prediction\": str, "
            "\"confidence\": 0-1, \"source_refs\": [str]}]}. "
            "Max 5 hypotheses. Prefer novel patterns over restating input."
        )
        prompt = f"""Memory context:
{memory_context}

Generate hypotheses worth testing.

JSON:"""
        raw = await self.generate(prompt=prompt, system=system, temperature=0.4, timeout=300.0, json_mode=True)
        parsed = self._parse_json(raw)
        items = parsed.get("hypotheses", [])
        return items if isinstance(items, list) else []

    async def evaluate_answer_quality(
        self,
        question: str,
        answer: str,
        reference_concepts: list[str],
        source_episodes: list[str],
    ) -> dict[str, Any]:
        """LLM-as-judge for semantic retention and groundedness."""
        from acme.evaluation.scoring import groundedness_score, semantic_retention_score

        fallback_retention = semantic_retention_score(answer, reference_concepts)
        fallback_grounded = groundedness_score(answer, source_episodes)

        system = (
            "You evaluate AI memory answers. Return ONLY valid JSON with keys: "
            "retention_score (0-1), groundedness_score (0-1), reasoning (string). "
            "retention_score: how well the answer captures reference concepts semantically — "
            "synonyms and paraphrases count (e.g. 'slow API' matches 'latency'). "
            "groundedness_score: 1.0 if supported by ingested episodes, lower if hallucinated "
            "or unsupported claims appear."
        )
        episodes_block = "\n".join(f"- {ep}" for ep in source_episodes)
        concepts_block = ", ".join(reference_concepts)
        prompt = f"""Question: {question}

Answer:
{answer}

Reference concepts (semantic match expected):
{concepts_block}

Ingested episodes:
{episodes_block}

JSON:"""
        try:
            raw = await self.generate(
                prompt=prompt,
                system=system,
                temperature=0.0,
                timeout=120.0,
                json_mode=True,
            )
            parsed = self._parse_json(raw)
            retention = float(parsed.get("retention_score", fallback_retention))
            grounded = float(parsed.get("groundedness_score", fallback_grounded))
            return {
                "retention_score": max(0.0, min(1.0, retention)),
                "groundedness_score": max(0.0, min(1.0, grounded)),
                "reasoning": parsed.get("reasoning", ""),
                "judge": "llm",
            }
        except Exception:
            return {
                "retention_score": fallback_retention,
                "groundedness_score": fallback_grounded,
                "reasoning": "Deterministic fallback — LLM judge unavailable.",
                "judge": "deterministic",
            }

    @staticmethod
    def _coerce_text(value: Any, default: str = "") -> str:
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = text.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence_match:
            text = fence_match.group(1).strip()
        brace_match = re.search(r"\{[\s\S]*\}", text)
        if brace_match:
            text = brace_match.group(0)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _to_extraction_result(data: dict[str, Any]) -> ExtractionResult:
        entities: list[GraphEntity] = []
        relations: list[GraphRelation] = []

        for item in data.get("entities", []):
            if not item.get("name"):
                continue
            kt = item.get("knowledge_type", "observation")
            try:
                knowledge_type = KnowledgeType(kt)
            except ValueError:
                knowledge_type = KnowledgeType.OBSERVATION
            entities.append(
                GraphEntity(
                    name=str(item["name"]),
                    entity_type=str(item.get("entity_type", "unknown")),
                    knowledge_type=knowledge_type,
                    properties=item.get("properties", {}),
                )
            )

        for item in data.get("relations", []):
            if not item.get("source") or not item.get("target"):
                continue
            kt = item.get("knowledge_type", "inference")
            try:
                knowledge_type = KnowledgeType(kt)
            except ValueError:
                knowledge_type = KnowledgeType.INFERENCE

            from acme.engines.deterministic import normalize_relation_type
            from acme.schemas import CausalRelationType

            raw_causal = item.get("causal_type") or item.get("relation_type", "related_to")
            causal_value = normalize_relation_type(str(raw_causal))
            try:
                causal_type = CausalRelationType(causal_value)
            except ValueError:
                causal_type = CausalRelationType.RELATED_TO

            relations.append(
                GraphRelation(
                    source=str(item["source"]),
                    target=str(item["target"]),
                    relation_type=str(item.get("relation_type", causal_type.value)),
                    causal_type=causal_type,
                    knowledge_type=knowledge_type,
                    confidence=float(item.get("confidence", 0.5)),
                    properties=item.get("properties", {}),
                )
            )

        return ExtractionResult(
            entities=entities,
            relations=relations,
            summary=data.get("summary"),
        )
