"""Memory chat demo API routes."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from acme.chat.schemas import (
    ChatMessageOut,
    ChatSendResponse,
    ChatSessionCreate,
    ChatSessionOut,
    MemoryStatsOut,
)
from acme.chat.service import chat_service
from acme.config import settings
from acme.db.session import get_session as get_db_session
from acme.engines.belief import BeliefEngine
from acme.graph.neo4j_client import neo4j_client
from acme.chat.schemas import BeliefBrief

router = APIRouter(prefix="/chat", tags=["chat"])

_STATIC = Path(__file__).resolve().parent / "static"


def _require_chat_enabled() -> None:
    if not settings.chat_demo_enabled:
        raise HTTPException(503, "Chat demo is disabled")


@router.post("/sessions", response_model=ChatSessionOut)
async def create_session(
    body: ChatSessionCreate | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> ChatSessionOut:
    _require_chat_enabled()
    return await chat_service.create_session(session, title=(body.title if body else None))


@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
async def read_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ChatSessionOut:
    _require_chat_enabled()
    row = await chat_service.get_session(session, session_id)
    if row is None:
        raise HTTPException(404, "Session not found")
    return chat_service._session_out(row)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    session_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[ChatMessageOut]:
    _require_chat_enabled()
    if await chat_service.get_session(session, session_id) is None:
        raise HTTPException(404, "Session not found")
    return await chat_service.list_messages(session, session_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatSendResponse)
async def send_message(
    session_id: UUID,
    message: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    session: AsyncSession = Depends(get_db_session),
) -> ChatSendResponse:
    _require_chat_enabled()
    uploads: list[tuple[str, str, bytes]] = []
    for f in files:
        if not f.filename:
            continue
        data = await f.read()
        uploads.append((f.filename, f.content_type or "", data))
    try:
        return await chat_service.send_message(
            session,
            neo4j_client,
            session_id=session_id,
            text=message,
            uploads=uploads or None,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/sessions/{session_id}/memory", response_model=MemoryStatsOut)
async def memory_stats(
    session_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> MemoryStatsOut:
    _require_chat_enabled()
    row = await chat_service.get_session(session, session_id)
    if row is None:
        raise HTTPException(404, "Session not found")
    return await chat_service.memory_stats(session, neo4j_client, tenant_id=row.tenant_id)


@router.get("/sessions/{session_id}/beliefs", response_model=list[BeliefBrief])
async def list_beliefs(
    session_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[BeliefBrief]:
    _require_chat_enabled()
    row = await chat_service.get_session(session, session_id)
    if row is None:
        raise HTTPException(404, "Session not found")
    engine = BeliefEngine(session, tenant_id=row.tenant_id)
    scores = await engine.list_beliefs(min_confidence=0.0)
    return [
        BeliefBrief(
            label=b.label,
            crs=b.crs,
            confidence=b.confidence,
            status=b.status.value if hasattr(b.status, "value") else str(b.status),
        )
        for b in scores[:20]
    ]


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_chat_enabled()
    try:
        return await chat_service.delete_session(session, neo4j_client, session_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/")
async def chat_ui() -> FileResponse:
    _require_chat_enabled()
    return FileResponse(_STATIC / "index.html")


@router.get("/assets/{path:path}")
async def chat_assets(path: str) -> FileResponse:
    _require_chat_enabled()
    target = (_STATIC / path).resolve()
    if not str(target).startswith(str(_STATIC.resolve())):
        raise HTTPException(404)
    if not target.is_file():
        raise HTTPException(404)
    return FileResponse(target)
