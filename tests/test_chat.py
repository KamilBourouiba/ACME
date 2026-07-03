"""Tests for the public memory chat demo."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from acme.chat.schemas import ChatMessageOut, ChatSendResponse, ChatSessionOut, MemoryStatsOut
from acme.chat.service import chat_service
from acme.config import settings
from acme.db.session import get_session
from acme.main import app


@pytest.fixture(autouse=True)
def _mock_lifecycle(monkeypatch):
    monkeypatch.setattr("acme.main.init_db", AsyncMock(return_value=None))
    monkeypatch.setattr("acme.main.neo4j_client.connect", AsyncMock(return_value=None))
    monkeypatch.setattr("acme.main.neo4j_client.close", AsyncMock(return_value=None))
    monkeypatch.setattr("acme.chat.cleanup.purge_legacy_demo_data", AsyncMock(return_value=[]))


@pytest.fixture
def client():
    async def _fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_session] = _fake_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_chat_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr(settings, "chat_demo_enabled", False)
    r = client.post("/api/v1/chat/sessions", json={})
    assert r.status_code == 503


def test_create_chat_session(client, monkeypatch):
    sid = uuid.uuid4()
    monkeypatch.setattr(settings, "chat_demo_enabled", True)
    monkeypatch.setattr(
        chat_service,
        "create_session",
        AsyncMock(
            return_value=ChatSessionOut(
                session_id=sid,
                tenant_id=f"chat-{sid}",
                title="New conversation",
                created_at=datetime.now(timezone.utc),
                skills=["browse_web", "search_memory"],
            )
        ),
    )
    r = client.post("/api/v1/chat/sessions", json={})
    assert r.status_code == 200
    assert r.json()["session_id"] == str(sid)


def test_chat_ui_available(client, monkeypatch):
    monkeypatch.setattr(settings, "chat_demo_enabled", True)
    r = client.get("/api/v1/chat/")
    assert r.status_code == 200
    assert "ACME Memory Chat" in r.text


def test_send_message_route(client, monkeypatch):
    sid = uuid.uuid4()
    mid = uuid.uuid4()
    monkeypatch.setattr(settings, "chat_demo_enabled", True)
    monkeypatch.setattr(
        chat_service,
        "send_message",
        AsyncMock(
            return_value=ChatSendResponse(
                message=ChatMessageOut(
                    id=mid,
                    role="assistant",
                    content="Hello from memory agent.",
                    created_at=datetime.now(timezone.utc),
                ),
                memory=MemoryStatsOut(
                    episode_count=2,
                    belief_count=1,
                    graph_entities=3,
                    promoted_beliefs=0,
                ),
            )
        ),
    )
    r = client.post(
        f"/api/v1/chat/sessions/{sid}/messages",
        data={"message": "Hi"},
    )
    assert r.status_code == 200
    assert "memory agent" in r.json()["message"]["content"]


def test_root_redirects_to_chat(client, monkeypatch):
    monkeypatch.setattr(settings, "chat_demo_enabled", True)
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (307, 302)
    assert "/api/v1/chat" in r.headers.get("location", "")


def test_chat_tools_catalog():
    from pathlib import Path

    tools = (Path(__file__).resolve().parents[1] / "acme/chat/tools.py").read_text()
    assert "browse_web" in tools
    assert "search_memory" in tools
    assert "remember" in tools
