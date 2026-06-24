"""Ablation environment toggles."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from acme.config import settings
from acme.orchestrator import ACMEOrchestrator
from acme.schemas import QueryRequest


@pytest.mark.asyncio
async def test_ablation_disable_contrarian():
    session = AsyncMock()
    graph = AsyncMock()
    llm = AsyncMock()
    llm.reason = AsyncMock(return_value={"answer": "ok", "confidence": 0.9, "reasoning": "r"})
    llm.contrarian_check = AsyncMock(return_value="challenge")

    orch = ACMEOrchestrator(session, graph, llm, tenant_id="default")
    orch.retrieval.build_context = AsyncMock(return_value=("ctx", []))
    orch.beliefs.list_beliefs = AsyncMock(return_value=[])
    orch.events.append = AsyncMock()
    session.add = MagicMock()

    async def _flush():
        for call in session.add.call_args_list:
            obj = call[0][0]
            if not getattr(obj, "id", None):
                obj.id = uuid4()

    session.flush = _flush
    session.commit = AsyncMock()

    with patch.object(settings, "ablation_disable_contrarian", False):
        await orch.query(QueryRequest(question="why?", challenge=False))
        llm.contrarian_check.assert_called()

    with patch.object(settings, "ablation_disable_contrarian", True):
        llm.contrarian_check.reset_mock()
        await orch.query(QueryRequest(question="why?", challenge=True))
        llm.contrarian_check.assert_not_called()
