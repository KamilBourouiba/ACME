"""Chat session service — agent loop, uploads, memory stats."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.chat.schemas import (
    AttachmentOut,
    BeliefBrief,
    ChatMessageOut,
    ChatSendResponse,
    ChatSessionOut,
    MemoryStatsOut,
    ToolCallOut,
)
from acme.chat.tools import (
    AGENT_SYSTEM,
    SKILL_NAMES,
    build_agent_prompt,
    parse_agent_step,
    run_tool,
)
from acme.config import settings
from acme.db.models import BeliefRecord, ChatMessage, ChatSession, Episode
from acme.graph.neo4j_client import Neo4jClient
from acme.llm.factory import llm_client
from acme.orchestrator import ACMEOrchestrator
from acme.schemas import ExperienceCreate, SourceType

logger = logging.getLogger("acme.chat.service")

_TEXT_MIMES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
        "application/xml",
        "text/html",
    }
)


def tenant_for_session(session_id: uuid.UUID) -> str:
    return f"chat-{session_id}"


def _decode_upload(name: str, mime: str, data: bytes) -> tuple[str, str]:
    lower = name.lower()
    if mime in _TEXT_MIMES or lower.endswith((".txt", ".md", ".json", ".csv", ".py", ".js", ".ts", ".yaml", ".yml")):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1", errors="replace")
        return text[:50_000], mime or "text/plain"
    return f"[Binary file {name}, {len(data)} bytes — describe contents in chat]", mime or "application/octet-stream"


class ChatService:
    async def create_session(
        self,
        session: AsyncSession,
        *,
        title: str | None = None,
    ) -> ChatSessionOut:
        sid = uuid.uuid4()
        tenant = tenant_for_session(sid)
        row = ChatSession(
            id=sid,
            tenant_id=tenant,
            title=(title or "New conversation").strip()[:256],
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return self._session_out(row)

    async def get_session(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
    ) -> ChatSession | None:
        result = await session.execute(select(ChatSession).where(ChatSession.id == session_id))
        return result.scalar_one_or_none()

    async def list_messages(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
    ) -> list[ChatMessageOut]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [self._message_out(r) for r in rows]

    async def memory_stats(
        self,
        session: AsyncSession,
        graph: Neo4jClient,
        *,
        tenant_id: str,
    ) -> MemoryStatsOut:
        ep_count = await session.scalar(
            select(func.count()).select_from(Episode).where(Episode.tenant_id == tenant_id)
        )
        bl_count = await session.scalar(
            select(func.count()).select_from(BeliefRecord).where(BeliefRecord.tenant_id == tenant_id)
        )
        promoted = await session.scalar(
            select(func.count())
            .select_from(BeliefRecord)
            .where(BeliefRecord.tenant_id == tenant_id, BeliefRecord.status == "belief")
        )
        entities = await graph.count_entities(tenant_id=tenant_id)
        return MemoryStatsOut(
            episode_count=int(ep_count or 0),
            belief_count=int(bl_count or 0),
            graph_entities=int(entities or 0),
            promoted_beliefs=int(promoted or 0),
        )

    async def send_message(
        self,
        db: AsyncSession,
        graph: Neo4jClient,
        *,
        session_id: uuid.UUID,
        text: str,
        uploads: list[tuple[str, str, bytes]] | None = None,
    ) -> ChatSendResponse:
        chat = await self.get_session(db, session_id)
        if chat is None:
            raise ValueError("Session not found")

        tenant_id = chat.tenant_id
        orch = ACMEOrchestrator(db, graph, llm_client, tenant_id=tenant_id)

        attachments_meta: list[dict[str, Any]] = []
        ingest_chunks: list[str] = []
        for name, mime, data in uploads or []:
            if len(data) > settings.chat_max_upload_bytes:
                raise ValueError(f"File too large: {name}")
            extracted, mime = _decode_upload(name, mime, data)
            attachments_meta.append(
                {
                    "name": name,
                    "mime": mime,
                    "size": len(data),
                    "preview": extracted[:400],
                    "text": extracted,
                }
            )
            ingest_chunks.append(f"Uploaded file '{name}':\n{extracted[:8000]}")

        user_content = text.strip()
        if not user_content and not attachments_meta:
            raise ValueError("Empty message")

        user_row = ChatMessage(
            session_id=session_id,
            role="user",
            content=user_content or "(file upload)",
            attachments=attachments_meta,
        )
        db.add(user_row)
        await db.flush()

        await orch.ingest_experience(
            ExperienceCreate(
                content=user_content or f"User uploaded: {', '.join(a['name'] for a in attachments_meta)}",
                action="chat_message",
                tags=["chat", "user"],
                source_type=SourceType.USER,
                context={"session_id": str(session_id)},
            )
        )
        for chunk in ingest_chunks:
            await orch.ingest_experience(
                ExperienceCreate(
                    content=chunk,
                    action="file_upload",
                    tags=["chat", "upload"],
                    source_type=SourceType.USER,
                    context={"session_id": str(session_id)},
                )
            )

        history_rows = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id, ChatMessage.role.in_(("user", "assistant")))
                .order_by(ChatMessage.created_at.asc())
            )
        ).scalars().all()
        history = [{"role": r.role, "content": r.content} for r in history_rows[:-1]]

        tool_trace: list[dict[str, Any]] = []
        tool_calls_out: list[ToolCallOut] = []
        beliefs_used: list[BeliefBrief] = []
        query_session_id: uuid.UUID | None = None
        final_message = ""

        for _ in range(settings.chat_max_tool_rounds):
            prompt = build_agent_prompt(
                history=history,
                tool_trace=tool_trace,
                user_message=user_content,
                attachment_names=[a["name"] for a in attachments_meta],
            )
            raw = await llm_client.generate(
                prompt=prompt,
                system=AGENT_SYSTEM,
                temperature=0.3,
                json_mode=True,
                timeout=120.0,
            )
            step = parse_agent_step(raw)
            if step["action"] == "tool" and step["tool"]:
                result = await run_tool(
                    step["tool"],
                    step["tool_input"],
                    orch=orch,
                    graph=graph,
                )
                tool_trace.append({"tool": step["tool"], "input": step["tool_input"], "result": result})
                tool_calls_out.append(
                    ToolCallOut(
                        tool=step["tool"],
                        input=step["tool_input"],
                        summary=result.get("summary", ""),
                        ok=bool(result.get("ok")),
                    )
                )
                if step["tool"] == "search_memory" and result.get("ok"):
                    detail = result.get("detail") or {}
                    for b in detail.get("beliefs") or []:
                        beliefs_used.append(
                            BeliefBrief(
                                label=str(b.get("label", "")),
                                crs=float(b.get("crs") or 0),
                                confidence=float(b.get("confidence") or 0),
                                status=str(b.get("status", "")),
                            )
                        )
                continue
            final_message = step.get("message") or raw.strip()
            break

        if not final_message:
            final_message = "I couldn't complete that request — try rephrasing or ask me to search memory."

        assistant_row = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=final_message,
            tool_calls=[t.model_dump() for t in tool_calls_out],
            beliefs_used=[b.model_dump() for b in beliefs_used],
            query_session_id=query_session_id,
        )
        db.add(assistant_row)
        chat.updated_at = datetime.now(timezone.utc)
        if chat.title == "New conversation" and user_content:
            chat.title = user_content[:80]
        await db.commit()
        await db.refresh(assistant_row)

        stats = await self.memory_stats(db, graph, tenant_id=tenant_id)
        return ChatSendResponse(
            message=self._message_out(assistant_row),
            memory=stats,
        )

    async def delete_session(
        self,
        db: AsyncSession,
        graph: Neo4jClient,
        session_id: uuid.UUID,
    ) -> dict[str, Any]:
        chat = await self.get_session(db, session_id)
        if chat is None:
            raise ValueError("Session not found")
        from acme.demo.reset import cleanup_demo_tenant

        stats = await cleanup_demo_tenant(db, graph, tenant_id=chat.tenant_id)
        await db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
        await db.execute(delete(ChatSession).where(ChatSession.id == session_id))
        await db.commit()
        return stats

    def _session_out(self, row: ChatSession) -> ChatSessionOut:
        return ChatSessionOut(
            session_id=row.id,
            tenant_id=row.tenant_id,
            title=row.title,
            created_at=row.created_at,
            skills=list(SKILL_NAMES),
        )

    def _message_out(self, row: ChatMessage) -> ChatMessageOut:
        return ChatMessageOut(
            id=row.id,
            role=row.role,
            content=row.content,
            attachments=[
                AttachmentOut(
                    name=a.get("name", ""),
                    mime=a.get("mime", ""),
                    size=int(a.get("size") or 0),
                    preview=str(a.get("preview", "")),
                )
                for a in (row.attachments or [])
            ],
            tool_calls=[ToolCallOut(**t) for t in (row.tool_calls or [])],
            beliefs_used=[BeliefBrief(**b) for b in (row.beliefs_used or [])],
            created_at=row.created_at,
        )


chat_service = ChatService()
