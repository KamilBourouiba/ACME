"""Vector retrieval over episodic embeddings — pgvector when available, JSONB fallback."""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from acme.config import settings
from acme.db.models import Episode
from acme.llm.embeddings import EmbeddingClient, cosine_similarity, deterministic_embed


class VectorRetrievalEngine:
    def __init__(self, session: AsyncSession, embedder: EmbeddingClient | None = None) -> None:
        self.session = session
        self.embedder = embedder or EmbeddingClient()
        self._pgvector: bool | None = None

    async def _use_pgvector(self) -> bool:
        if not settings.pgvector_enabled:
            return False
        if self._pgvector is not None:
            return self._pgvector
        try:
            result = await self.session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            self._pgvector = result.scalar_one_or_none() is not None
        except Exception:
            self._pgvector = False
        return self._pgvector

    def _vec_literal(self, vec: list[float]) -> str:
        return "[" + ",".join(str(v) for v in vec) + "]"

    async def embed_episode(self, episode: Episode) -> None:
        vec = await self.embedder.embed(episode.content)
        episode.embedding = vec
        if await self._use_pgvector():
            dim = len(vec)
            if dim != 256:
                vec = deterministic_embed(episode.content, dim=256)
                episode.embedding = vec
            try:
                async with self.session.begin_nested():
                    await self.session.execute(
                        text(
                            "UPDATE episodes SET embedding_vec = CAST(:vec AS vector) WHERE id = :id"
                        ),
                        {"vec": self._vec_literal(vec), "id": str(episode.id)},
                    )
            except Exception:
                self._pgvector = False
        await self.session.flush()

    async def search(
        self,
        question: str,
        limit: int = 5,
        *,
        tenant_id: str = "default",
    ) -> list[Episode]:
        if await self._use_pgvector():
            return await self._search_pgvector(question, limit, tenant_id=tenant_id)
        return await self._search_jsonb(question, limit, tenant_id=tenant_id)

    async def _search_pgvector(
        self, question: str, limit: int, *, tenant_id: str
    ) -> list[Episode]:
        query_vec = await self.embedder.embed(question)
        if len(query_vec) != 256:
            query_vec = deterministic_embed(question, dim=256)
        stmt = text(
            """
            SELECT id FROM episodes
            WHERE tenant_id = :tenant_id
              AND memory_tier NOT IN ('archive', 'deleted')
              AND embedding_vec IS NOT NULL
            ORDER BY embedding_vec <=> CAST(:query_vec AS vector)
            LIMIT :limit
            """
        )
        rows = (
            await self.session.execute(
                stmt,
                {
                    "tenant_id": tenant_id,
                    "query_vec": self._vec_literal(query_vec),
                    "limit": limit,
                },
            )
        ).all()
        if not rows:
            return await self._search_jsonb(question, limit, tenant_id=tenant_id)

        ids = [row[0] for row in rows]
        episodes = (
            await self.session.execute(select(Episode).where(Episode.id.in_(ids)))
        ).scalars().all()
        order = {str(ep_id): idx for idx, ep_id in enumerate(ids)}
        episodes.sort(key=lambda ep: order.get(str(ep.id), 999))
        return episodes

    async def _search_jsonb(
        self, question: str, limit: int, *, tenant_id: str
    ) -> list[Episode]:
        query_vec = await self.embedder.embed(question)
        stmt = (
            select(Episode)
            .where(Episode.tenant_id == tenant_id)
            .where(Episode.memory_tier.notin_(["archive", "deleted"]))
            .where(Episode.embedding.is_not(None))
            .order_by(Episode.created_at.desc())
            .limit(500)
        )
        episodes = list((await self.session.execute(stmt)).scalars().all())
        scored = [
            (cosine_similarity(query_vec, ep.embedding or []), ep)
            for ep in episodes
            if ep.embedding
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:limit]]
