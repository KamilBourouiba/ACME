"""Smoke tests for Belief Observatory API."""

from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["product"] == "belief-observatory"


def test_trace():
    r = client.get("/api/trace")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) >= 4
    assert len(data["steps"]) >= 4
