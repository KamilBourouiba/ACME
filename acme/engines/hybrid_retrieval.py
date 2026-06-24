"""Hybrid graph + vector retrieval with cross-verification."""

from sqlalchemy.ext.asyncio import AsyncSession

from acme.engines.retrieval import RetrievalEngine
from acme.engines.vector_retrieval import VectorRetrievalEngine
from acme.graph.neo4j_client import Neo4jClient
from acme.llm.embeddings import EmbeddingClient
from acme.schemas import BeliefScore


class HybridRetrievalEngine:
    def __init__(
        self,
        graph: Neo4jClient,
        session: AsyncSession,
        embedder: EmbeddingClient | None = None,
        *,
        tenant_id: str = "default",
    ) -> None:
        self.graph = RetrievalEngine(graph, tenant_id=tenant_id)
        self.vector = VectorRetrievalEngine(session, embedder)
        self.tenant_id = tenant_id

    async def build_context(
        self,
        question: str,
        beliefs: list[BeliefScore] | None = None,
    ) -> tuple[str, list[str]]:
        graph_context, entities = await self.graph.build_context(question, beliefs)
        vector_eps = await self.vector.search(question, limit=5, tenant_id=self.tenant_id)

        vector_lines = [
            f"Episode (similarity-ranked): {ep.content[:300]}"
            for ep in vector_eps
        ]
        vector_block = (
            "Vector-retrieved episodes:\n" + "\n".join(vector_lines)
            if vector_lines
            else "Vector-retrieved episodes: none"
        )

        entity_terms = {e.lower() for e in entities}
        verified = 0
        for ep in vector_eps:
            if any(term in ep.content.lower() for term in entity_terms if len(term) > 3):
                verified += 1
        cross = (
            f"Graph entities {len(entities)} align with {verified}/{len(vector_eps)} vector episodes"
            if vector_eps
            else "No vector episodes to cross-verify"
        )

        merged = f"{graph_context}\n\n{vector_block}\n\nCross-verification: {cross}"
        extra_entities = entities.copy()
        for ep in vector_eps:
            for tag in ep.tags or []:
                if tag not in extra_entities:
                    extra_entities.append(tag)

        return merged, extra_entities
