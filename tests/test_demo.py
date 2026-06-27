import pytest
from fastapi.testclient import TestClient

from acme.config import settings
from acme.demo.agents import DEMO_AGENTS
from acme.demo.schemas import DemoAgentOut, DemoChannelOut, DemoStateOut
from acme.demo.service import demo_service
from acme.main import app


def test_demo_agents_config():
    assert len(DEMO_AGENTS) == 10
    tenants = {a.tenant_id for a in DEMO_AGENTS}
    assert len(tenants) == 10


def test_demo_routes_disabled_by_default():
    client = TestClient(app)
    r = client.get("/api/v1/demo/state")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_demo_routes_when_enabled(monkeypatch):
    async def fake_state(*, selected_agent=None, selected_channel=None):
        return DemoStateOut(
            running=True,
            model="gpt-5.4",
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

    async def fake_reset():
        return True, "Demo reset complete.", [{"tenant_id": "demo-nexus-alex"}]

    monkeypatch.setattr(settings, "demo_enabled", True)
    monkeypatch.setattr(demo_service, "get_state", fake_state)
    monkeypatch.setattr(demo_service, "reset", fake_reset)
    client = TestClient(app)
    r = client.get("/api/v1/demo/state")
    assert r.status_code == 200
    data = r.json()
    assert data["running"] is True
    assert len(data["agents"]) == 10

    reset = client.post("/api/v1/demo/reset")
    assert reset.status_code == 200
    assert reset.json()["ok"] is True
