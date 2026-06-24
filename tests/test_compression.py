import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from acme.db.models import Episode
from acme.engines.compression import CompressionEngine
from acme.schemas import CompressionRequest


def _episode(content: str, tags: list[str]) -> Episode:
    ep = Episode(content=content, tags=tags)
    ep.id = uuid.uuid4()
    ep.created_at = datetime.now(timezone.utc)
    return ep


def test_cluster_episodes_by_tag():
    episodes = [
        _episode("A failed due to latency", ["latency"]),
        _episode("B failed due to latency", ["latency"]),
        _episode("C failed due to latency", ["latency"]),
        _episode("Unrelated event", ["billing"]),
    ]
    clusters = CompressionEngine._cluster_episodes(episodes, min_episodes=3)
    assert "latency" in clusters
    assert len(clusters["latency"]) == 3
    assert "billing" not in clusters


def test_cluster_ignores_small_groups():
    episodes = [
        _episode("One", ["rare"]),
        _episode("Two", ["rare"]),
    ]
    clusters = CompressionEngine._cluster_episodes(episodes, min_episodes=3)
    assert clusters == {}


@pytest.mark.asyncio
async def test_compress_creates_abstraction():
    session = AsyncMock()

    def capture_add(obj):
        if hasattr(obj, "id") and obj.id is None:
            obj.id = uuid.uuid4()
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)

    session.add = MagicMock(side_effect=capture_add)
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    episodes = [
        _episode("Customer A timeout on checkout", ["latency"]),
        _episode("Customer B timeout on checkout", ["latency"]),
        _episode("Customer C timeout on checkout", ["latency"]),
    ]

    graph = AsyncMock()
    graph.upsert_entity = AsyncMock(return_value="Abstraction: Latency causes failures")
    graph.upsert_relation = AsyncMock(return_value={"rel_id": 1})

    ollama = AsyncMock()
    ollama.compress_episodes = AsyncMock(
        return_value={
            "abstraction": "Latency frequently causes checkout failures",
            "confidence": 0.82,
            "supporting_patterns": ["timeout", "checkout"],
            "reasoning": "All three episodes mention checkout timeouts",
        }
    )

    engine = CompressionEngine(session, graph, ollama)
    engine.events = AsyncMock()
    engine.events.append = AsyncMock(return_value=uuid.uuid4())
    engine.beliefs = AsyncMock()
    engine.beliefs.sync_from_relation = AsyncMock()
    engine.forgetting = AsyncMock()
    engine.forgetting.touch = AsyncMock()
    engine._load_episodes = AsyncMock(return_value=episodes)

    result = await engine.compress(CompressionRequest(tags=["latency"], min_episodes=3))

    assert result.abstractions_created == 1
    assert result.episodes_compressed == 3
    assert "Latency" in result.abstractions[0].label
    ollama.compress_episodes.assert_called_once()


@pytest.mark.asyncio
async def test_compress_skips_low_confidence():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    episodes = [_episode(f"Event {i}", ["noise"]) for i in range(3)]

    ollama = AsyncMock()
    ollama.compress_episodes = AsyncMock(
        return_value={"abstraction": "Weak pattern", "confidence": 0.2}
    )

    engine = CompressionEngine(session, AsyncMock(), ollama)
    engine.events = AsyncMock()
    engine.events.append = AsyncMock(return_value=uuid.uuid4())
    engine._load_episodes = AsyncMock(return_value=episodes)

    result = await engine.compress(
        CompressionRequest(min_episodes=3, min_confidence=0.6)
    )

    assert result.abstractions_created == 0
    session.add.assert_not_called()
