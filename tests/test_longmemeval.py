"""Tests for LongMemEval adapter (offline / deterministic judge)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from acme.evaluation.baseline_rag import RAGBaselineRunner
from acme.evaluation.longmemeval import (
    ACMELongMemEvalBackend,
    LongMemEvalItem,
    RAGLongMemEvalBackend,
    build_transcript_memory_context,
    default_dataset_path,
    format_session_content,
    get_anscheck_prompt,
    judge_longmemeval_answer,
    load_longmemeval_dataset,
    parse_session_date,
    parse_yes_no_judge,
    run_longmemeval,
)
from acme.schemas import QueryResponse


FIXTURE = Path(__file__).resolve().parents[1] / "data" / "longmemeval" / "fixture_oracle_sample.json"


def test_fixture_loads():
    items = load_longmemeval_dataset(FIXTURE)
    assert len(items) >= 6
    assert any(i.question_type == "knowledge-update" for i in items)


def test_default_dataset_path_points_to_fixture_when_full_missing():
    path = default_dataset_path()
    assert path.is_file()


def test_format_session_content():
    text = format_session_content(
        "s1",
        "2023/01/01",
        [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}],
    )
    assert "User: Hello" in text
    assert "Assistant: Hi" in text


def test_official_judge_prompt_knowledge_update():
    prompt = get_anscheck_prompt(
        "knowledge-update",
        "Q?",
        "25:50",
        "Your PB is 25 minutes 50 seconds.",
    )
    assert "updated answer" in prompt.lower()


def test_parse_yes_no_judge():
    assert parse_yes_no_judge("Yes.") is True
    assert parse_yes_no_judge("no") is False


@pytest.mark.asyncio
async def test_deterministic_judge_abstention():
    item = load_longmemeval_dataset(FIXTURE, limit=1)[0]
    item = type(item)(
        question_id="x_abs",
        question_type=item.question_type,
        question=item.question,
        answer=item.answer,
        question_date=item.question_date,
        haystack_session_ids=item.haystack_session_ids,
        haystack_dates=item.haystack_dates,
        haystack_sessions=item.haystack_sessions,
    )
    ok, _ = await judge_longmemeval_answer(
        None, item, "I cannot answer — insufficient memory.", use_llm_judge=False
    )
    assert ok is True


@pytest.mark.asyncio
async def test_run_longmemeval_rag_offline():
    items = load_longmemeval_dataset(FIXTURE, limit=2)
    llm = AsyncMock()
    llm.reason = AsyncMock(
        return_value={
            "answer": items[0].answer,
            "reasoning": "from memory",
            "confidence": 0.9,
            "entities_used": [],
        }
    )
    runner = RAGBaselineRunner(llm)
    runner.embedder.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])

    backend = RAGLongMemEvalBackend(runner)
    result = await run_longmemeval(
        backend,
        items,
        llm_judge=None,
        dataset_path=FIXTURE,
        use_llm_judge=False,
    )
    assert result.items_run == 2
    assert 0.0 <= result.accuracy <= 1.0


def test_parse_session_date_ordering():
    assert parse_session_date("2023/05/25 (Thu) 20:21") < parse_session_date(
        "2023/06/01 (Thu) 00:58"
    )


def test_build_transcript_memory_context_newest_first():
    from types import SimpleNamespace

    old = SimpleNamespace(
        content="old session",
        context={"session_date": "2023/05/25 (Thu) 20:21"},
    )
    new = SimpleNamespace(
        content="new session",
        context={"session_date": "2023/06/01 (Thu) 00:58"},
    )
    ctx = build_transcript_memory_context([old, new], question_date="2023/06/02")
    assert ctx.index("new session") < ctx.index("old session")
    assert "MOST RECENT" in ctx


@pytest.mark.asyncio
async def test_judge_handles_numeric_answers():
    item = load_longmemeval_dataset(FIXTURE, limit=1)[0]
    item = LongMemEvalItem(
        question_id=item.question_id,
        question_type="knowledge-update",
        question=item.question,
        answer="120",
        question_date=item.question_date,
        haystack_session_ids=item.haystack_session_ids,
        haystack_dates=item.haystack_dates,
        haystack_sessions=item.haystack_sessions,
    )
    ok, _ = await judge_longmemeval_answer(
        None, item, "The total is 120 pages.", use_llm_judge=False
    )
    assert ok is True


@pytest.mark.asyncio
async def test_acme_backend_ingest_and_answer():
    item = json.loads(FIXTURE.read_text())[0]
    lme_item = load_longmemeval_dataset(FIXTURE, limit=1)[0]

    orchestrator = MagicMock()
    orchestrator.tenant_id = "default"
    orchestrator.session = AsyncMock()
    orchestrator.graph = AsyncMock()
    orchestrator.graph.delete_benchmark_graph = AsyncMock(
        return_value={"entities_deleted": 0, "relations_deleted": 0}
    )
    orchestrator.graph.prune_orphan_entities = AsyncMock(return_value=0)
    orchestrator.session.execute = AsyncMock()
    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []
    orchestrator.session.execute.return_value = empty_result
    orchestrator.beliefs = MagicMock()
    orchestrator.beliefs.list_beliefs = AsyncMock(return_value=[])
    orchestrator.session.commit = AsyncMock()
    orchestrator.ingest_experience = AsyncMock()
    orchestrator.query = AsyncMock(
        return_value=QueryResponse(
            answer="test answer",
            confidence=0.8,
            reasoning="ok",
            session_id="00000000-0000-0000-0000-000000000001",
        )
    )

    backend = ACMELongMemEvalBackend(orchestrator)
    await backend.reset()
    await backend.ingest_item(lme_item)
    answer = await backend.answer(lme_item)

    assert answer == "test answer"
    assert orchestrator.ingest_experience.await_count == len(item["haystack_sessions"])
