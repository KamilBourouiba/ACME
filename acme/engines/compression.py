"""Compression engine — pattern discovery and abstraction generation."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.db.models import AbstractionRecord, Episode
from acme.engines.belief import BeliefEngine
from acme.engines.forgetting import ForgettingEngine
from acme.events.store import EventStore
from acme.graph.neo4j_client import Neo4jClient
from acme.llm.base import BaseLLMClient
from acme.schemas import (
    AbstractionResponse,
    CompressionRequest,
    CompressionResponse,
    GraphEntity,
    GraphRelation,
    KnowledgeType,
)


class CompressionEngine:
    """Convert clusters of episodes into confidence-weighted abstractions."""

    def __init__(
        self,
        session: AsyncSession,
        graph: Neo4jClient,
        ollama: BaseLLMClient,
        *,
        tenant_id: str = "default",
    ) -> None:
        self.session = session
        self.graph = graph
        self.ollama = ollama
        self.tenant_id = tenant_id
        self.events = EventStore(session)
        self.beliefs = BeliefEngine(session)
        self.forgetting = ForgettingEngine(session)

    async def compress(self, request: CompressionRequest) -> CompressionResponse:
        episodes = await self._load_episodes(request.tags, request.min_episodes, request.limit)
        clusters = self._cluster_episodes(episodes, request.min_episodes)

        abstractions: list[AbstractionResponse] = []
        episodes_compressed = 0

        for cluster_key, cluster in clusters.items():
            if len(cluster) < request.min_episodes:
                continue

            result = await self.ollama.compress_episodes(
                [ep.content for ep in cluster],
                cluster_key=cluster_key,
            )
            if not result.get("abstraction"):
                continue

            confidence = float(result.get("confidence", 0.5))
            if confidence < request.min_confidence:
                continue

            episode_ids = [ep.id for ep in cluster]
            for ep in cluster:
                await self.forgetting.touch(ep.id)

            abstraction = AbstractionRecord(
                label=result["abstraction"],
                pattern=cluster_key,
                source_episode_ids=[str(eid) for eid in episode_ids],
                episode_count=len(cluster),
                confidence=confidence,
                properties={
                    "supporting_patterns": result.get("supporting_patterns", []),
                    "reasoning": result.get("reasoning", ""),
                },
            )
            self.session.add(abstraction)
            await self.session.flush()

            await self._project_to_graph(abstraction, cluster_key)
            episodes_compressed += len(cluster)
            abstractions.append(self._to_response(abstraction))

        await self.events.append(
            "compression.completed",
            {
                "abstractions_created": len(abstractions),
                "episodes_compressed": episodes_compressed,
                "clusters_processed": len(clusters),
            },
        )
        await self.session.commit()

        return CompressionResponse(
            abstractions_created=len(abstractions),
            episodes_compressed=episodes_compressed,
            abstractions=abstractions,
        )

    async def list_abstractions(self, min_confidence: float = 0.0) -> list[AbstractionResponse]:
        stmt = (
            select(AbstractionRecord)
            .where(AbstractionRecord.confidence >= min_confidence)
            .order_by(AbstractionRecord.confidence.desc())
        )
        result = await self.session.execute(stmt)
        return [self._to_response(row) for row in result.scalars().all()]

    async def _load_episodes(
        self,
        tags: list[str] | None,
        min_episodes: int,
        limit: int,
    ) -> list[Episode]:
        stmt = (
            select(Episode)
            .where(Episode.memory_tier.notin_(["archive", "deleted"]))
            .order_by(Episode.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        episodes = list(result.scalars().all())

        if tags:
            tag_set = {t.lower() for t in tags}
            episodes = [
                ep for ep in episodes if tag_set.intersection({t.lower() for t in (ep.tags or [])})
            ]

        return episodes

    @staticmethod
    def _cluster_episodes(episodes: list[Episode], min_episodes: int) -> dict[str, list[Episode]]:
        by_tag: dict[str, list[Episode]] = defaultdict(list)
        for episode in episodes:
            if episode.tags:
                for tag in episode.tags:
                    by_tag[tag.lower()].append(episode)
            else:
                by_tag["untagged"].append(episode)

        return {key: eps for key, eps in by_tag.items() if len(eps) >= min_episodes}

    async def _project_to_graph(self, abstraction: AbstractionRecord, cluster_key: str) -> None:
        entity = GraphEntity(
            name=f"Abstraction: {abstraction.label[:120]}",
            entity_type="abstraction",
            knowledge_type=KnowledgeType.HYPOTHESIS,
            properties={
                "abstraction_id": str(abstraction.id),
                "pattern": cluster_key,
                "episode_count": abstraction.episode_count,
            },
        )
        entity_name = await self.graph.upsert_entity(entity, tenant_id=self.tenant_id)

        for episode_id in abstraction.source_episode_ids[:20]:
            relation = GraphRelation(
                source=entity_name,
                target=f"Episode:{episode_id[:8]}",
                relation_type="COMPRESSED_FROM",
                knowledge_type=KnowledgeType.INFERENCE,
                confidence=abstraction.confidence,
                properties={"episode_id": episode_id},
            )
            await self.graph.upsert_relation(relation)

        await self.beliefs.sync_from_relation(
            f"entity:{entity_name}",
            abstraction.label,
            GraphRelation(
                source=entity_name,
                target=cluster_key,
                relation_type="PATTERN",
                knowledge_type=KnowledgeType.HYPOTHESIS,
                confidence=abstraction.confidence,
            ),
        )

    @staticmethod
    def _to_response(record: AbstractionRecord) -> AbstractionResponse:
        return AbstractionResponse(
            id=record.id,
            label=record.label,
            pattern=record.pattern,
            episode_count=record.episode_count,
            confidence=record.confidence,
            source_episode_ids=[UUID(eid) for eid in record.source_episode_ids],
            created_at=record.created_at,
        )
