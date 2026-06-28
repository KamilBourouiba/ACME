"""Memory retrieval — graph search + belief context assembly."""

import json
import re

from acme.graph.neo4j_client import Neo4jClient
from acme.schemas import BeliefScore


class RetrievalEngine:
    def __init__(self, graph: Neo4jClient, *, tenant_id: str = "default") -> None:
        self.graph = graph
        self.tenant_id = tenant_id

    async def build_context(
        self,
        question: str,
        beliefs: list[BeliefScore] | None = None,
        *,
        demo_mode: bool = False,
    ) -> tuple[str, list[str]]:
        terms = self._extract_terms(question)
        entities = await self.graph.search_entities(terms, tenant_id=self.tenant_id)

        entity_names: list[str] = []
        context_parts: list[str] = []

        for entity in entities:
            name = entity["name"]
            entity_names.append(name)
            outgoing = [r for r in entity.get("outgoing", []) if r.get("target")]
            context_parts.append(
                f"Entity: {name} ({entity.get('entity_type')}, {entity.get('knowledge_type')})\n"
                f"Relations: {json.dumps(outgoing, ensure_ascii=False)}"
            )

            neighborhood = await self.graph.get_neighborhood(name, depth=1, tenant_id=self.tenant_id)
            edge_limit = 50 if demo_mode else 10
            for edge in neighborhood[:edge_limit]:
                context_parts.append(
                    f"  {edge['source']} --[{edge['relation_type']}]--> {edge['target']} "
                    f"(confidence={edge.get('confidence')}, type={edge.get('knowledge_type')})"
                )

        if beliefs:
            belief_limit = len(beliefs) if demo_mode else 10
            belief_lines = [
                f"Belief: {b.label} (confidence={b.confidence:.2f}, "
                f"support={b.supporting_evidence}, contradict={b.contradicting_evidence})"
                for b in beliefs[:belief_limit]
            ]
            context_parts.append("Tracked beliefs:\n" + "\n".join(belief_lines))

        if not context_parts:
            context_parts.append("No relevant memory found in graph.")

        return "\n\n".join(context_parts), entity_names

    @staticmethod
    def _extract_terms(text: str) -> list[str]:
        words = re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", text)
        seen: set[str] = set()
        terms: list[str] = []
        for word in words:
            lower = word.lower()
            if lower not in seen:
                seen.add(lower)
                terms.append(word)
        return terms[:12]
