"""Public multi-agent demo routes (no API key — read-only + server-side loop)."""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from acme.config import settings
from acme.demo.schemas import (
    DemoAgentOut,
    DemoDeployIn,
    DemoDeployOut,
    DemoPauseOut,
    DemoResetOut,
    DemoStateOut,
    DemoVisitorSayIn,
    DemoVisitorSayOut,
    DemoVisitorUnlockIn,
    DemoVisitorUnlockOut,
)
from acme.demo.service import demo_service

router = APIRouter(prefix="/demo", tags=["demo"])


def _demo_disabled() -> None:
    if not settings.demo_enabled:
        raise HTTPException(status_code=503, detail="Live demo is disabled on this deployment")


@router.get("/state", response_model=DemoStateOut)
async def demo_state(
    agent: str | None = Query(default=None, description="Highlight beliefs for this agent id"),
    channel: str | None = Query(default=None, description="Filter/highlight channel"),
) -> DemoStateOut:
    _demo_disabled()
    return await demo_service.get_state(selected_agent=agent, selected_channel=channel)


@router.get("/agents/{agent_id}", response_model=DemoAgentOut)
async def demo_agent_detail(agent_id: str) -> DemoAgentOut:
    _demo_disabled()
    detail = await demo_service.get_agent_detail(agent_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown agent")
    return detail


@router.post("/reset", response_model=DemoResetOut)
async def demo_reset() -> DemoResetOut:
    _demo_disabled()
    ok, message, stats = await demo_service.reset()
    if not ok:
        raise HTTPException(status_code=429, detail=message)
    return DemoResetOut(ok=True, tenants_reset=len(stats), stats=stats)


@router.post("/pause", response_model=DemoPauseOut)
async def demo_pause() -> DemoPauseOut:
    _demo_disabled()
    return await demo_service.pause()


@router.post("/resume", response_model=DemoPauseOut)
async def demo_resume() -> DemoPauseOut:
    _demo_disabled()
    return await demo_service.resume()


@router.post("/deploy", response_model=DemoDeployOut)
async def demo_deploy(body: DemoDeployIn | None = None) -> DemoDeployOut:
    _demo_disabled()
    payload = body or DemoDeployIn()
    try:
        result = await demo_service.deploy(
            repo=payload.repo,
            branch=payload.branch,
            token=payload.token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub deploy failed: {exc}") from exc
    return DemoDeployOut(ok=True, **result)


@router.get("/preview", response_class=HTMLResponse)
async def demo_preview() -> HTMLResponse:
    _demo_disabled()
    html = demo_service.build_preview_html()
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-cache",
            "Content-Security-Policy": "frame-ancestors *",
        },
    )


@router.get("/ui-screenshot/{shot_id}.png")
async def demo_ui_screenshot(shot_id: str) -> Response:
    _demo_disabled()
    if not shot_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid screenshot id")
    data = demo_service.get_ui_screenshot(shot_id)
    if not data:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-cache"})


@router.post("/unlock", response_model=DemoVisitorUnlockOut)
async def demo_unlock(body: DemoVisitorUnlockIn) -> DemoVisitorUnlockOut:
    _demo_disabled()
    try:
        return await demo_service.unlock_visitor(secret=body.secret)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/say", response_model=DemoVisitorSayOut)
async def demo_say(body: DemoVisitorSayIn) -> DemoVisitorSayOut:
    _demo_disabled()
    try:
        return await demo_service.handle_visitor_say(
            secret=body.secret,
            channel=body.channel,
            message=body.message,
        )
    except ValueError as exc:
        status = 403 if "secret" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


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
