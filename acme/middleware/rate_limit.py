"""Simple in-memory rate limiting for expensive benchmark endpoints."""

import time
from collections import defaultdict

from fastapi import HTTPException, Request

from acme.config import settings

_WINDOW_SECONDS = 3600
_buckets: dict[str, list[float]] = defaultdict(list)


def check_benchmark_rate_limit(request: Request) -> None:
    limit = settings.benchmark_rate_limit_per_hour
    if limit <= 0:
        return

    client = request.client.host if request.client else "unknown"
    tenant = getattr(request.state, "tenant_id", settings.default_tenant_id)
    key = f"{tenant}:{client}"
    now = time.time()
    window_start = now - _WINDOW_SECONDS
    _buckets[key] = [t for t in _buckets[key] if t >= window_start]

    if len(_buckets[key]) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Benchmark rate limit exceeded ({limit}/hour)",
        )
    _buckets[key].append(now)
