from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from api.config import SERVICES
from api.db import get_pool
from api.models import LeadIn, LeadOut, ServiceItem, ServicesOut

router = APIRouter()


@router.get("/services", response_model=ServicesOut)
async def list_services() -> ServicesOut:
    return ServicesOut(items=[ServiceItem(**s) for s in SERVICES])


@router.post("/lead", response_model=LeadOut)
async def create_lead(body: LeadIn) -> LeadOut:
    pool = await get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    async with pool.acquire() as conn:
        lead_id = await conn.fetchval(
            "INSERT INTO leads (email, company, message, created_at) VALUES ($1, $2, $3, $4) RETURNING id",
            body.email,
            body.company,
            body.message,
            datetime.now(timezone.utc),
        )
    return LeadOut(id=lead_id)
