from acme.middleware.rate_limit import check_benchmark_rate_limit
from acme.middleware.tenant import verify_api_key
from acme.config import settings
from fastapi import HTTPException
from unittest.mock import MagicMock
import pytest


def test_verify_api_key_skipped_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "")
    request = MagicMock()
    verify_api_key(request)


def test_verify_api_key_rejects_invalid(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "secret")
    request = MagicMock()
    request.headers.get.return_value = "wrong"
    with pytest.raises(HTTPException) as exc:
        verify_api_key(request)
    assert exc.value.status_code == 401


def test_benchmark_rate_limit_disabled(monkeypatch):
    monkeypatch.setattr(settings, "benchmark_rate_limit_per_hour", 0)
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.state.tenant_id = "default"
    check_benchmark_rate_limit(request)
