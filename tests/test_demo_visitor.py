import pytest
from fastapi.testclient import TestClient

from acme.config import settings
from acme.demo.agents import DEMO_AGENTS
from acme.demo.schemas import DemoAgentOut, DemoChannelOut, DemoStateOut
from acme.demo.service import demo_service
from acme.main import app


def _fake_state(**overrides):
    base = DemoStateOut(
        running=True,
        model="gpt-test",
        tick=1,
        channels=[
            DemoChannelOut(id="general", name="general", topic="Squad", emoji="💬"),
        ],
        agents=[
            DemoAgentOut(
                id=a.id,
                name=a.name,
                role=a.role,
                tenant_id=a.tenant_id,
                color=a.color,
                initials=a.initials,
                channels=list(a.channels),
            )
            for a in DEMO_AGENTS
        ],
        messages=[],
    )
    return base.model_copy(update=overrides)


@pytest.mark.asyncio
async def test_visitor_unlock_and_say(monkeypatch):
    async def fake_reply(agent, *, channel, visitor_text):
        return f"{agent.name} heard you: {visitor_text}"

    async def fake_ingest(*args, **kwargs):
        return None

    async def fake_get_state(*, selected_agent=None, selected_channel=None):
        return _fake_state()

    async def fake_notify(_event):
        return None

    monkeypatch.setattr(settings, "demo_enabled", True)
    monkeypatch.setattr(settings, "demo_visitor_secret", "LeanLean")
    monkeypatch.setattr(settings, "demo_visitor_say_cooldown_sec", 0)
    monkeypatch.setattr(demo_service, "_agent_reply_to_visitor", fake_reply)
    monkeypatch.setattr(demo_service, "_ingest_visitor_exchange", fake_ingest)
    monkeypatch.setattr(demo_service, "get_state", fake_get_state)
    monkeypatch.setattr(demo_service, "_notify", fake_notify)

    client = TestClient(app)

    bad = client.post("/api/v1/demo/unlock", json={"secret": "wrong"})
    assert bad.status_code == 403

    ok = client.post("/api/v1/demo/unlock", json={"secret": "LeanLean"})
    assert ok.status_code == 200
    assert ok.json()["ok"] is True

    say = client.post(
        "/api/v1/demo/say",
        json={"secret": "LeanLean", "channel": "general", "message": "Hello squad"},
    )
    assert say.status_code == 200
    body = say.json()
    assert body["ok"] is True
    assert body["your_message"]["kind"] == "visitor"
    assert body["your_message"]["content"] == "Hello squad"
    assert len(body["replies"]) >= 1
    assert "Hello squad" in body["replies"][0]["content"]


def test_visitor_say_invalid_channel(monkeypatch):
    async def fake_reply(agent, *, channel, visitor_text):
        return "ok"

    async def fake_ingest(*args, **kwargs):
        return None

    async def fake_get_state(*, selected_agent=None, selected_channel=None):
        return _fake_state()

    async def fake_notify(_event):
        return None

    monkeypatch.setattr(settings, "demo_enabled", True)
    monkeypatch.setattr(settings, "demo_visitor_secret", "LeanLean")
    monkeypatch.setattr(settings, "demo_visitor_say_cooldown_sec", 0)
    monkeypatch.setattr(demo_service, "_agent_reply_to_visitor", fake_reply)
    monkeypatch.setattr(demo_service, "_ingest_visitor_exchange", fake_ingest)
    monkeypatch.setattr(demo_service, "get_state", fake_get_state)
    monkeypatch.setattr(demo_service, "_notify", fake_notify)

    client = TestClient(app)
    r = client.post(
        "/api/v1/demo/say",
        json={"secret": "LeanLean", "channel": "nope", "message": "hi"},
    )
    assert r.status_code == 400
