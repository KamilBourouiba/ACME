"""Public multi-agent demo routes (no API key — read-only + server-side loop)."""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from acme.config import settings
from acme.demo.schemas import DemoAgentOut, DemoStateOut
from acme.demo.service import demo_service

router = APIRouter(prefix="/demo", tags=["demo"])


def _demo_disabled() -> None:
    if not settings.demo_enabled:
        raise HTTPException(status_code=503, detail="Live demo is disabled on this deployment")


@router.get("/state", response_model=DemoStateOut)
async def demo_state(
    agent: str | None = Query(default=None, description="Highlight beliefs for this agent id"),
) -> DemoStateOut:
    _demo_disabled()
    return await demo_service.get_state(selected_agent=agent)


@router.get("/agents/{agent_id}", response_model=DemoAgentOut)
async def demo_agent_detail(agent_id: str) -> DemoAgentOut:
    _demo_disabled()
    detail = await demo_service.get_agent_detail(agent_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown agent")
    return detail


@router.get("/events")
async def demo_events() -> StreamingResponse:
    _demo_disabled()

    async def stream():
        queue = demo_service.subscribe()
        try:
            state = await demo_service.get_state()
            yield f"data: {json.dumps({'type': 'snapshot', 'state': state.model_dump()})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            demo_service.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
