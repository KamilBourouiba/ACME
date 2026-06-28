from fastapi import APIRouter

from api.db import get_pool

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    pool = await get_pool()
    if pool is None:
        return {"status": "degraded", "database": "not_configured"}
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok", "database": "connected"}
