"""Nexus Advisory lead-capture API (demo squad backend)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

DATABASE_URL = os.environ.get("DATABASE_URL", "")


class LeadIn(BaseModel):
    email: EmailStr
    company: str = Field(min_length=1, max_length=200)
    message: str = Field(default="", max_length=2000)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = None
    if DATABASE_URL:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5, ssl="require")
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id BIGSERIAL PRIMARY KEY,
                    email TEXT NOT NULL,
                    company TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
    app.state.pool = pool
    yield
    if pool:
        await pool.close()


app = FastAPI(title="Nexus Advisory API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    pool = app.state.pool
    if pool is None:
        return {"status": "degraded", "database": "not_configured"}
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok", "database": "connected"}


@app.post("/api/lead")
async def create_lead(body: LeadIn) -> dict[str, str | int]:
    pool = app.state.pool
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
    return {"id": lead_id, "status": "accepted"}
