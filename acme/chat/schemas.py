"""Pydantic schemas for the memory chat demo."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=256)


class ChatSessionOut(BaseModel):
    session_id: UUID
    tenant_id: str
    title: str
    created_at: datetime
    skills: list[str] = Field(default_factory=list)


class AttachmentOut(BaseModel):
    name: str
    mime: str
    size: int
    preview: str = ""


class ToolCallOut(BaseModel):
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    summary: str
    ok: bool = True


class BeliefBrief(BaseModel):
    label: str
    crs: float
    confidence: float
    status: str


class ChatMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    attachments: list[AttachmentOut] = Field(default_factory=list)
    tool_calls: list[ToolCallOut] = Field(default_factory=list)
    beliefs_used: list[BeliefBrief] = Field(default_factory=list)
    created_at: datetime


class ChatSendResponse(BaseModel):
    message: ChatMessageOut
    memory: MemoryStatsOut


class MemoryStatsOut(BaseModel):
    episode_count: int
    belief_count: int
    graph_entities: int
    promoted_beliefs: int
