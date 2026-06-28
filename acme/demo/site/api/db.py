from __future__ import annotations

import os

import asyncpg

from api.config import DATABASE_URL

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool | None:
    return _pool


async def init_db() -> asyncpg.Pool | None:
    global _pool
    if not DATABASE_URL:
        return None
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


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
