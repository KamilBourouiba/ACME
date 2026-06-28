from fastapi import APIRouter

from api.db import get_pool

router = APIRouter()


@router.get("/health")
async def health():
    pool = await get_pool()
    return {
        "status": "ok",
        "database": "connected" if pool is not None else "degraded",
        "product": "erebor",
    }
