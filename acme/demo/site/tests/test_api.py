"""Smoke tests for Nexus API (run on VM or CI)."""

def test_services_shape():
    from api.config import SERVICES

    assert len(SERVICES) >= 3
    assert "title" in SERVICES[0]
