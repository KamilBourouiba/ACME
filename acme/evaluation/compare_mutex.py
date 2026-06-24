"""Per-tenant mutex for benchmark compare runs — prevents sandbox cleanup races."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

_active: set[str] = set()
_guard = asyncio.Lock()


class CompareAlreadyRunningError(Exception):
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        super().__init__(f"Benchmark compare already running for tenant {tenant_id}")


def is_compare_running(tenant_id: str) -> bool:
    return tenant_id in _active


@asynccontextmanager
async def compare_slot(tenant_id: str):
    async with _guard:
        if tenant_id in _active:
            raise CompareAlreadyRunningError(tenant_id)
        _active.add(tenant_id)
    try:
        yield
    finally:
        async with _guard:
            _active.discard(tenant_id)


def reset_compare_mutex_for_tests() -> None:
    """Test helper — clear in-process compare locks."""
    _active.clear()
