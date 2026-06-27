import pytest
from fastapi.testclient import TestClient

from acme.config import settings
from acme.demo.agents import DEMO_AGENTS
from acme.demo.schemas import DemoAgentOut, DemoStateOut
from acme.demo.service import demo_service
from acme.main import app


def test_demo_agents_config():
    assert len(DEMO_AGENTS) == 3
    tenants = {a.tenant_id for a in DEMO_AGENTS}
    assert len(tenants) == 3


def test_demo_routes_disabled_by_default():
    client = TestClient(app)
    r = client.get("/api/v1/demo/state")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_demo_routes_when_enabled(monkeypatch):
    async def fake_state(*, selected_agent=None):
        return DemoStateOut(
            running=True,
            model="gpt-5.4",
            tick=1,
            agents=[
                DemoAgentOut(
                    id=a.id,
                    name=a.name,
                    role=a.role,
                    tenant_id=a.tenant_id,
                    color=a.color,
                )
                for a in DEMO_AGENTS
            ],
            messages=[],
        )

    monkeypatch.setattr(settings, "demo_enabled", True)
    monkeypatch.setattr(demo_service, "get_state", fake_state)
    client = TestClient(app)
    r = client.get("/api/v1/demo/state")
    assert r.status_code == 200
    data = r.json()
    assert data["running"] is True
    assert len(data["agents"]) == 3
