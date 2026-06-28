from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from api.config import FEATURES, METRICS, PRICING
from api.db import get_pool
from api.models import FeatureItem, FeaturesOut, WaitlistIn, WaitlistOut

router = APIRouter()


@router.get("/features", response_model=FeaturesOut)
async def list_features() -> FeaturesOut:
    return FeaturesOut(items=[FeatureItem(**f) for f in FEATURES])


@router.get("/pricing")
async def list_pricing() -> dict:
    return PRICING


@router.get("/metrics")
async def platform_metrics() -> dict:
    pool = await get_pool()
    count = METRICS["waitlist_count"]
    if pool:
        row = await pool.fetchval("SELECT COUNT(*) FROM waitlist")
        if row is not None:
            count = int(row) + METRICS["waitlist_count"]
    return {**METRICS, "waitlist_count": count}


@router.post("/waitlist", response_model=WaitlistOut)
async def join_waitlist(body: WaitlistIn) -> WaitlistOut:
    pool = await get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    async with pool.acquire() as conn:
        wid = await conn.fetchval(
            """
            INSERT INTO waitlist (email, company, role, created_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (email) DO UPDATE SET company = EXCLUDED.company
            RETURNING id
            """,
            body.email,
            body.company,
            body.role,
            datetime.now(timezone.utc),
        )
    return WaitlistOut(id=wid)
