"""In-process runtime counters for observability."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

_lock = threading.Lock()
_stats: dict[str, int | float | str | None] = {
    "embedding_requests": 0,
    "embedding_failures": 0,
    "embedding_provider": "unknown",
    "last_embedding_at": None,
    "compare_jobs_completed": 0,
    "compare_jobs_failed": 0,
    "last_compare_duration_sec": None,
    "last_compare_at": None,
}


def record_embedding(*, provider: str, success: bool) -> None:
    with _lock:
        _stats["embedding_requests"] = int(_stats["embedding_requests"]) + 1
        if not success:
            _stats["embedding_failures"] = int(_stats["embedding_failures"]) + 1
        _stats["embedding_provider"] = provider
        _stats["last_embedding_at"] = datetime.now(timezone.utc).isoformat()


def record_compare_job(*, success: bool, duration_sec: float | None = None) -> None:
    with _lock:
        if success:
            _stats["compare_jobs_completed"] = int(_stats["compare_jobs_completed"]) + 1
        else:
            _stats["compare_jobs_failed"] = int(_stats["compare_jobs_failed"]) + 1
        if duration_sec is not None:
            _stats["last_compare_duration_sec"] = round(duration_sec, 2)
        _stats["last_compare_at"] = datetime.now(timezone.utc).isoformat()


def snapshot() -> dict:
    with _lock:
        return dict(_stats)
