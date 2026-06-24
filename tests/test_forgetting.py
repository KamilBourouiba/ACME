import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from acme.db.models import Episode
from acme.engines.forgetting import ForgettingEngine
from acme.schemas import ForgettingRequest, MemoryTier


def _episode(
    *,
    tier: str = "hot",
    access_count: int = 0,
    importance: float = 1.0,
    days_old: int = 0,
    tags: list[str] | None = None,
) -> Episode:
    now = datetime.now(timezone.utc)
    ep = Episode(
        content="Test episode content",
        tags=tags or [],
        memory_tier=tier,
        importance_score=importance,
        access_count=access_count,
        last_accessed_at=now - timedelta(days=days_old),
        created_at=now - timedelta(days=days_old),
    )
    ep.id = uuid.uuid4()
    return ep


def test_compute_importance_high_for_recent_accessed():
    ep = _episode(access_count=5, days_old=1)
    score = ForgettingEngine.compute_importance(ep)
    assert score >= 0.5


def test_compute_importance_low_for_stale_unused():
    ep = _episode(access_count=0, days_old=120, importance=0.3)
    score = ForgettingEngine.compute_importance(ep)
    assert score < 0.15


def test_target_tier_mapping():
    assert ForgettingEngine._target_tier(0.8, "hot") == MemoryTier.HOT
    assert ForgettingEngine._target_tier(0.4, "hot") == MemoryTier.WARM
    assert ForgettingEngine._target_tier(0.15, "hot") == MemoryTier.COLD
    assert ForgettingEngine._target_tier(0.05, "hot") == MemoryTier.ARCHIVE


@pytest.mark.asyncio
async def test_run_dry_run_reports_transitions():
    session = AsyncMock()
    stale = _episode(access_count=0, days_old=100, importance=0.2)
    session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=lambda: [stale])))
    )

    engine = ForgettingEngine(session)
    engine.events = AsyncMock()
    result = await engine.run(ForgettingRequest(dry_run=True))

    assert result.processed == 1
    assert result.dry_run is True
    assert result.archived >= 0
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_run_archives_low_importance_episode():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    stale = _episode(access_count=0, days_old=200, importance=0.2)
    session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=lambda: [stale])))
    )

    engine = ForgettingEngine(session)
    engine.events = AsyncMock()
    engine.events.append = AsyncMock(return_value=uuid.uuid4())

    result = await engine.run(ForgettingRequest(dry_run=False))

    assert stale.memory_tier == MemoryTier.ARCHIVE.value
    assert stale.archived_content == "Test episode content"
    assert stale.content == "[archived]"
    assert result.archived == 1
    session.commit.assert_called_once()
