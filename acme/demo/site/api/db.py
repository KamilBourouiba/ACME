"""Postgres pool — optional; API boots even if DB is temporarily unreachable."""

from __future__ import annotations

import logging
import os

import asyncpg

from api.config import DATABASE_URL

logger = logging.getLogger("erebor.db")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool | None:
    return _pool


async def init_db() -> asyncpg.Pool | None:
    global _pool
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set — trail persistence disabled")
        return None
    try:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10, ssl="require")
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS investigation_trail (
                    id BIGSERIAL PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        return _pool
    except Exception as exc:
        logger.warning("Postgres unavailable at startup: %s", exc)
        _pool = None
        return None


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
