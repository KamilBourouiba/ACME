"""Forgetting engine — memory lifecycle and importance-based pruning."""

from datetime import datetime, timezone
from math import exp
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.config import settings
from acme.db.models import Episode
from acme.events.store import EventStore
from acme.schemas import (
    EpisodeMemoryStatus,
    ForgettingRequest,
    ForgettingResponse,
    MemoryTier,
)


class ForgettingEngine:
    """Lifecycle: HOT → WARM → COLD → ARCHIVE → DELETE."""

    TIER_ORDER = [
        MemoryTier.HOT,
        MemoryTier.WARM,
        MemoryTier.COLD,
        MemoryTier.ARCHIVE,
    ]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.events = EventStore(session)

    async def run(self, request: ForgettingRequest) -> ForgettingResponse:
        stmt = (
            select(Episode)
            .where(Episode.memory_tier != "deleted")
            .order_by(Episode.created_at.asc())
            .limit(request.limit)
        )
        if request.tier:
            stmt = stmt.where(Episode.memory_tier == request.tier.value)

        result = await self.session.execute(stmt)
        episodes = list(result.scalars().all())

        tier_changes: dict[str, int] = {t.value: 0 for t in self.TIER_ORDER}
        tier_changes["deleted"] = 0
        archived = 0
        deleted = 0
        now = datetime.now(timezone.utc)

        for episode in episodes:
            importance = self.compute_importance(episode, now)
            episode.importance_score = importance
            new_tier = self._target_tier(importance, episode.memory_tier)

            if (
                episode.memory_tier == MemoryTier.ARCHIVE.value
                and importance < settings.forgetting_delete_threshold
                and request.delete_enabled
                and episode.archived_at
                and (now - self._ensure_aware(episode.archived_at)).days
                >= settings.forgetting_delete_after_days
            ):
                if request.dry_run:
                    tier_changes["deleted"] += 1
                    deleted += 1
                else:
                    await self.session.delete(episode)
                    tier_changes["deleted"] += 1
                    deleted += 1
                continue

            if new_tier.value == episode.memory_tier:
                continue

            if request.dry_run:
                tier_changes[new_tier.value] = tier_changes.get(new_tier.value, 0) + 1
                if new_tier == MemoryTier.ARCHIVE:
                    archived += 1
                continue

            if new_tier == MemoryTier.ARCHIVE:
                episode.archived_content = episode.content
                episode.content = "[archived]"
                episode.archived_at = now
                archived += 1

            episode.memory_tier = new_tier.value
            episode.tier_changed_at = now
            tier_changes[new_tier.value] = tier_changes.get(new_tier.value, 0) + 1

        if not request.dry_run:
            await self.events.append(
                "forgetting.completed",
                {
                    "processed": len(episodes),
                    "tier_changes": tier_changes,
                    "archived": archived,
                    "deleted": deleted,
                },
            )
            await self.session.commit()

        return ForgettingResponse(
            processed=len(episodes),
            dry_run=request.dry_run,
            tier_changes=tier_changes,
            archived=archived,
            deleted=deleted,
        )

    async def list_episodes(
        self,
        tier: MemoryTier | None = None,
        limit: int = 50,
    ) -> list[EpisodeMemoryStatus]:
        stmt = select(Episode).where(Episode.memory_tier != "deleted").order_by(
            Episode.importance_score.desc()
        ).limit(limit)
        if tier:
            stmt = stmt.where(Episode.memory_tier == tier.value)

        result = await self.session.execute(stmt)
        now = datetime.now(timezone.utc)
        return [self._to_status(ep, now) for ep in result.scalars().all()]

    async def touch(self, episode_id: UUID) -> None:
        stmt = select(Episode).where(Episode.id == episode_id)
        result = await self.session.execute(stmt)
        episode = result.scalar_one_or_none()
        if episode is None:
            return
        episode.access_count += 1
        episode.last_accessed_at = datetime.now(timezone.utc)
        await self.session.flush()

    @classmethod
    def compute_importance(cls, episode: Episode, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        confidence = min(1.0, max(0.1, episode.importance_score or 0.5))
        usage = min(1.0, episode.access_count / settings.forgetting_usage_cap)
        recency = cls._recency_factor(episode.last_accessed_at or episode.created_at, now)
        outcome = cls._outcome_factor(episode)
        return round(confidence * usage * recency * outcome, 4)

    @classmethod
    def _target_tier(cls, importance: float, current_tier: str) -> MemoryTier:
        if importance >= settings.forgetting_hot_threshold:
            return MemoryTier.HOT
        if importance >= settings.forgetting_warm_threshold:
            return MemoryTier.WARM
        if importance >= settings.forgetting_cold_threshold:
            return MemoryTier.COLD
        return MemoryTier.ARCHIVE

    @staticmethod
    def _recency_factor(last_access: datetime, now: datetime) -> float:
        last_access = ForgettingEngine._ensure_aware(last_access)
        days = max(0, (now - last_access).days)
        if days <= settings.forgetting_recency_full_days:
            return 1.0
        decay = exp(-days / settings.forgetting_recency_decay_days)
        return max(0.1, min(1.0, decay))

    @staticmethod
    def _outcome_factor(episode: Episode) -> float:
        tags = {t.lower() for t in (episode.tags or [])}
        if "critical" in tags or "important" in tags:
            return 1.0
        if "failure" in tags:
            return 0.7
        return 0.85

    @staticmethod
    def _ensure_aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @classmethod
    def _to_status(cls, episode: Episode, now: datetime) -> EpisodeMemoryStatus:
        return EpisodeMemoryStatus(
            id=episode.id,
            memory_tier=MemoryTier(episode.memory_tier),
            importance_score=cls.compute_importance(episode, now),
            access_count=episode.access_count,
            last_accessed_at=episode.last_accessed_at,
            created_at=episode.created_at,
            archived=episode.memory_tier == MemoryTier.ARCHIVE.value,
        )
