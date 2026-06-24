import pytest
from unittest.mock import AsyncMock, MagicMock

from acme.observability.metrics import collect_metrics


@pytest.mark.asyncio
async def test_collect_metrics_empty():
    session = AsyncMock()
    row = MagicMock()
    row.one.return_value = (0, None, None)
    session.execute = AsyncMock(side_effect=[
        row,
        MagicMock(all=lambda: []),
        MagicMock(one=lambda: (0, None)),
        MagicMock(all=lambda: []),
        MagicMock(scalar_one=lambda: 0),
    ])
    metrics = await collect_metrics(session, tenant_id="default")
    assert metrics["tenant_id"] == "default"
    assert metrics["beliefs"]["total"] == 0
