"""Smoke tests for Erebor intelligence API."""

from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["product"] == "erebor"


def test_catalog():
    r = client.get("/api/catalog")
    assert r.status_code == 200
    sources = r.json()["sources"]
    assert len(sources) >= 3
    ids = {s["id"] for s in sources}
    assert "github" in ids
    assert "openalex" in ids


def test_seed_graph():
    r = client.get("/api/graph")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) >= 3
    assert len(data["edges"]) >= 2
