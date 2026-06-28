from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from api import oss_clients
from api.config import OSS_SOURCES, SEED_GRAPH
from api.db import get_pool
from api.models import CatalogOut, GraphOut, SearchOut, TrailIn, TrailOut

router = APIRouter()


@router.get("/catalog", response_model=CatalogOut)
async def catalog() -> CatalogOut:
    return CatalogOut(sources=OSS_SOURCES)


@router.get("/graph", response_model=GraphOut)
async def seed_graph() -> GraphOut:
    return GraphOut(**SEED_GRAPH)


@router.get("/search", response_model=SearchOut)
async def unified_search(q: str = Query(..., min_length=2, max_length=120)) -> SearchOut:
    groups = []
    try:
        gh = await oss_clients.github_search(q)
        if gh:
            groups.append({"source": "GitHub", "items": gh})
    except Exception:
        pass
    try:
        oa = await oss_clients.openalex_search(q)
        if oa:
            groups.append({"source": "OpenAlex", "items": oa})
    except Exception:
        pass
    try:
        geo = await oss_clients.nominatim_search(q)
        if geo:
            groups.append({"source": "Nominatim", "items": geo})
    except Exception:
        pass
    if not groups:
        raise HTTPException(status_code=502, detail="All OSS sources unavailable")
    return SearchOut(query=q, groups=groups)


@router.get("/github/{owner}/{repo}")
async def github_detail(owner: str, repo: str) -> dict:
    try:
        return await oss_clients.github_repo(owner, repo)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/openalex/works/{work_id}")
async def openalex_detail(work_id: str) -> dict:
    try:
        return await oss_clients.openalex_work(work_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/geo/{place_id}")
async def geo_detail(place_id: str) -> dict:
    try:
        return await oss_clients.nominatim_place(place_id.replace("geo:", ""))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/trail", response_model=TrailOut)
async def log_trail(body: TrailIn) -> TrailOut:
    pool = await get_pool()
    if pool is None:
        return TrailOut(ok=True, persisted=False)
    async with pool.acquire() as conn:
        tid = await conn.fetchval(
            """
            INSERT INTO investigation_trail (event_type, payload, created_at)
            VALUES ($1, $2::jsonb, $3)
            RETURNING id
            """,
            body.type,
            body.model_dump_json(),
            datetime.now(timezone.utc),
        )
    return TrailOut(ok=True, persisted=True, id=tid)
