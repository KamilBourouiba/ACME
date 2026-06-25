"""LongMemEval adapter — industry-standard long-term memory benchmark.

Official dataset: https://github.com/xiaowu0162/LongMemEval
Uses oracle history (evidence sessions only) for cost-efficient evaluation.
Scoring follows the official yes/no LLM judge prompts from evaluate_qa.py.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from acme.evaluation.baseline_memgpt import MemGPTBaselineRunner, _MemGPTMemory
from acme.evaluation.baseline_rag import RAGBaselineRunner
from acme.evaluation.sandbox import (
    LONGMEMEVAL_TAG,
    cleanup_longmemeval_state,
    longmemeval_source_id,
    longmemeval_tags,
)
from acme.llm.base import BaseLLMClient
from acme.schemas import ContradictionRequest, ExperienceCreate, QueryRequest, SourceType
from acme.db.models import Episode
from acme.config import settings

SystemName = Literal["acme", "rag", "memgpt"]

QUESTION_TYPES = (
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "temporal-reasoning",
    "knowledge-update",
)


@dataclass(frozen=True)
class LongMemEvalItem:
    question_id: str
    question_type: str
    question: str
    answer: str
    question_date: str
    haystack_session_ids: list[str]
    haystack_dates: list[str]
    haystack_sessions: list[list[dict[str, Any]]]

    @property
    def is_abstention(self) -> bool:
        return str(self.question_id).endswith("_abs")


@dataclass
class LongMemEvalItemResult:
    question_id: str
    question_type: str
    question: str
    expected_answer: str
    hypothesis: str
    correct: bool
    judge_response: str
    error: str | None = None


@dataclass
class LongMemEvalRunResult:
    system: SystemName
    dataset_path: str
    items_run: int
    accuracy: float
    accuracy_by_type: dict[str, float]
    item_counts_by_type: dict[str, int]
    results: list[LongMemEvalItemResult] = field(default_factory=list)
    judge: str = "longmemeval_official_prompt"

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "dataset_path": self.dataset_path,
            "items_run": self.items_run,
            "accuracy": self.accuracy,
            "accuracy_by_type": self.accuracy_by_type,
            "item_counts_by_type": self.item_counts_by_type,
            "judge": self.judge,
            "results": [
                {
                    "question_id": r.question_id,
                    "question_type": r.question_type,
                    "question": r.question,
                    "expected_answer": r.expected_answer,
                    "hypothesis": r.hypothesis,
                    "correct": r.correct,
                    "judge_response": r.judge_response,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


class LongMemEvalMemoryBackend(Protocol):
    name: SystemName

    async def reset(self) -> None: ...

    async def ingest_item(self, item: LongMemEvalItem) -> None: ...

    async def answer(self, item: LongMemEvalItem) -> str: ...


def default_dataset_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    full = root / "data" / "longmemeval" / "longmemeval_oracle.json"
    if full.is_file():
        return full
    return root / "data" / "longmemeval" / "fixture_oracle_sample.json"


def load_longmemeval_dataset(
    path: str | Path,
    *,
    question_types: list[str] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[LongMemEvalItem]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Expected JSON array in {path}")

    items: list[LongMemEvalItem] = []
    for entry in raw:
        item = LongMemEvalItem(
            question_id=str(entry["question_id"]),
            question_type=str(entry["question_type"]),
            question=str(entry["question"]),
            answer=str(entry["answer"]),
            question_date=str(entry.get("question_date", "")),
            haystack_session_ids=list(entry.get("haystack_session_ids", [])),
            haystack_dates=list(entry.get("haystack_dates", [])),
            haystack_sessions=list(entry.get("haystack_sessions", [])),
        )
        if question_types and item.question_type not in question_types:
            if not (item.is_abstention and "abstention" in question_types):
                continue
        items.append(item)

    if offset:
        items = items[offset:]
    if limit is not None:
        items = items[:limit]
    return items


def format_session_content(
    session_id: str,
    session_date: str,
    turns: list[dict[str, Any]],
) -> str:
    lines = [f"[Chat session {session_id} | {session_date}]"]
    for turn in turns:
        role = str(turn.get("role", "user")).capitalize()
        content = str(turn.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def parse_session_date(session_date: str) -> int:
    """Sortable YYYYMMDD from LongMemEval date strings."""
    if not session_date:
        return 0
    try:
        date_part = session_date.strip().split()[0]
        year, month, day = date_part.split("/")
        return int(year) * 10000 + int(month) * 100 + int(day)
    except (ValueError, IndexError):
        return 0


def build_transcript_memory_context(
    episodes: list[Episode],
    *,
    question_date: str = "",
) -> str:
    """Transcript-first context: newest sessions first for knowledge-update resolution."""
    ranked = sorted(
        episodes,
        key=lambda ep: parse_session_date(str((ep.context or {}).get("session_date", ""))),
        reverse=True,
    )
    parts = [
        "Chat session transcripts (newest first). When facts conflict across sessions, "
        "use the MOST RECENT session as the current truth.",
    ]
    if question_date:
        parts.append(f"Question date: {question_date}")
    for index, episode in enumerate(ranked):
        session_date = (episode.context or {}).get("session_date", "unknown")
        label = "MOST RECENT SESSION" if index == 0 else f"Older session #{index + 1}"
        parts.append(f"--- {label} ({session_date}) ---\n{episode.content}")
    return "\n\n".join(parts)


async def fetch_longmemeval_episodes(orchestrator, question_id: str) -> list[Episode]:
    """All sandbox episodes for one LongMemEval question."""
    from sqlalchemy import select

    tenant_id = getattr(orchestrator, "tenant_id", "default")
    tag = f"lme:{question_id}"
    stmt = (
        select(Episode)
        .where(Episode.tenant_id == tenant_id)
        .where(Episode.tags.contains([LONGMEMEVAL_TAG]))
        .where(Episode.tags.contains([tag]))
        .order_by(Episode.created_at.asc())
    )
    return list((await orchestrator.session.execute(stmt)).scalars().all())


async def retrieve_longmemeval_episodes(orchestrator, item: LongMemEvalItem) -> list[Episode]:
    """Oracle: use all tagged sessions; larger haystacks: vector + temporal re-rank."""
    tags = longmemeval_tags(item.question_id)
    all_eps = await fetch_longmemeval_episodes(orchestrator, item.question_id)
    if len(all_eps) <= 12:
        return all_eps

    vector = orchestrator.vector
    limit = max(settings.vector_search_limit, 8)
    if hasattr(vector, "search_tagged"):
        candidates = await vector.search_tagged(
            item.question,
            tags,
            limit=limit,
            tenant_id=getattr(orchestrator, "tenant_id", "default"),
        )
    else:
        candidates = await vector.search(
            item.question,
            limit=limit,
            tenant_id=getattr(orchestrator, "tenant_id", "default"),
        )
    if not candidates:
        return all_eps

    candidate_ids = {str(ep.id) for ep in candidates}
    merged = [ep for ep in all_eps if str(ep.id) in candidate_ids]
    if not merged:
        merged = candidates
    return sorted(
        merged,
        key=lambda ep: parse_session_date(str((ep.context or {}).get("session_date", ""))),
        reverse=True,
    )[:limit]


def get_anscheck_prompt(
    question_type: str,
    question: str,
    answer: str,
    response: str,
    *,
    abstention: bool = False,
) -> str:
    """Official LongMemEval judge prompts (evaluate_qa.py)."""
    question = str(question)
    answer = str(answer)
    response = str(response)
    if not abstention:
        if question_type in ("single-session-user", "single-session-assistant", "multi-session"):
            template = (
                "I will give you a question, a correct answer, and a response from a model. "
                "Please answer yes if the response contains the correct answer. Otherwise, answer no. "
                "If the response is equivalent to the correct answer or contains all the intermediate "
                "steps to get the correct answer, you should also answer yes. If the response only "
                "contains a subset of the information required by the answer, answer no. \n\n"
                "Question: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\n"
                "Is the model response correct? Answer yes or no only."
            )
            return template.format(question, answer, response)
        if question_type == "temporal-reasoning":
            template = (
                "I will give you a question, a correct answer, and a response from a model. "
                "Please answer yes if the response contains the correct answer. Otherwise, answer no. "
                "If the response is equivalent to the correct answer or contains all the intermediate "
                "steps to get the correct answer, you should also answer yes. If the response only "
                "contains a subset of the information required by the answer, answer no. In addition, "
                "do not penalize off-by-one errors for the number of days. If the question asks for "
                "the number of days/weeks/months, etc., and the model makes off-by-one errors "
                "(e.g., predicting 19 days when the answer is 18), the model's response is still correct. "
                "\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\n"
                "Is the model response correct? Answer yes or no only."
            )
            return template.format(question, answer, response)
        if question_type == "knowledge-update":
            template = (
                "I will give you a question, a correct answer, and a response from a model. "
                "Please answer yes if the response contains the correct answer. Otherwise, answer no. "
                "If the response contains some previous information along with an updated answer, "
                "the response should be considered as correct as long as the updated answer is "
                "the required answer.\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\n"
                "Is the model response correct? Answer yes or no only."
            )
            return template.format(question, answer, response)
        if question_type == "single-session-preference":
            template = (
                "I will give you a question, a rubric for desired personalized response, and a "
                "response from a model. Please answer yes if the response satisfies the desired "
                "response. Otherwise, answer no. The model does not need to reflect all the points "
                "in the rubric. The response is correct as long as it recalls and utilizes the "
                "user's personal information correctly.\n\nQuestion: {}\n\nRubric: {}\n\n"
                "Model Response: {}\n\nIs the model response correct? Answer yes or no only."
            )
            return template.format(question, answer, response)
        raise ValueError(f"Unsupported question_type: {question_type}")

    template = (
        "I will give you an unanswerable question, an explanation, and a response from a model. "
        "Please answer yes if the model correctly identifies the question as unanswerable. "
        "The model could say that the information is incomplete, or some other information is "
        "given but the asked information is not.\n\nQuestion: {}\n\nExplanation: {}\n\n"
        "Model Response: {}\n\nDoes the model correctly identify the question as unanswerable? "
        "Answer yes or no only."
    )
    return template.format(question, answer, response)


def parse_yes_no_judge(text: str) -> bool:
    return "yes" in text.strip().lower()


def deterministic_judge(item: LongMemEvalItem, hypothesis: str) -> bool:
    """Offline fallback when LLM judge is unavailable (tests / CI)."""
    hyp = hypothesis.lower()
    if item.is_abstention:
        markers = (
            "don't know",
            "do not know",
            "cannot answer",
            "can't answer",
            "insufficient",
            "not mentioned",
            "no information",
            "unanswerable",
            "not available",
        )
        return any(m in hyp for m in markers)

    answer = item.answer.lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", answer) if len(t) >= 4]
    if not tokens:
        return answer in hyp
    hits = sum(1 for t in tokens if t in hyp)
    return hits / len(tokens) >= 0.4


async def judge_longmemeval_answer(
    llm: BaseLLMClient | None,
    item: LongMemEvalItem,
    hypothesis: str,
    *,
    use_llm_judge: bool = True,
) -> tuple[bool, str]:
    hypothesis = str(hypothesis) if hypothesis is not None else ""
    if not hypothesis.strip():
        return False, "empty hypothesis"

    if use_llm_judge and llm is not None:
        prompt = get_anscheck_prompt(
            item.question_type,
            item.question,
            item.answer,
            hypothesis,
            abstention=item.is_abstention,
        )
        try:
            response = await llm.generate(prompt=prompt, temperature=0.0, timeout=120.0)
            text = str(response).strip()
            return parse_yes_no_judge(text), text
        except Exception as exc:
            label = deterministic_judge(item, hypothesis)
            return label, f"deterministic_fallback:{exc}"

    label = deterministic_judge(item, hypothesis)
    return label, "deterministic"


class ACMELongMemEvalBackend:
    name: SystemName = "acme"

    def __init__(self, orchestrator) -> None:
        self.orchestrator = orchestrator

    async def reset(self) -> None:
        tenant_id = getattr(self.orchestrator, "tenant_id", "default")
        await cleanup_longmemeval_state(
            self.orchestrator.session,
            self.orchestrator.graph,
            tenant_id=tenant_id,
        )

    async def ingest_item(self, item: LongMemEvalItem) -> None:
        tags = longmemeval_tags(item.question_id)
        sessions = list(
            zip(
                item.haystack_session_ids,
                item.haystack_dates,
                item.haystack_sessions,
                strict=False,
            )
        )
        sessions.sort(key=lambda row: parse_session_date(row[1]))
        for session_id, session_date, turns in sessions:
            content = format_session_content(session_id, session_date, turns)
            await self.orchestrator.ingest_experience(
                ExperienceCreate(
                    content=content,
                    tags=tags,
                    source_type=SourceType.USER,
                    source_id=longmemeval_source_id(item.question_id, session_id),
                    context={
                        "session_date": session_date,
                        "session_id": session_id,
                        "question_type": item.question_type,
                        "longmemeval_id": item.question_id,
                    },
                )
            )
        if item.question_type == "knowledge-update":
            await self._apply_knowledge_update_demotion(item)

    async def _apply_knowledge_update_demotion(self, item: LongMemEvalItem) -> None:
        """Demote beliefs tied only to older sessions when a newer session exists (KU)."""
        if settings.ablation_disable_belief_sync:
            return
        from sqlalchemy import select

        from acme.db.models import BeliefRecord

        episodes = await fetch_longmemeval_episodes(self.orchestrator, item.question_id)
        if len(episodes) < 2:
            return
        ranked = sorted(
            episodes,
            key=lambda ep: parse_session_date(str((ep.context or {}).get("session_date", ""))),
        )
        oldest_source = ranked[0].source_id
        newest_source = ranked[-1].source_id
        if not oldest_source or not newest_source or oldest_source == newest_source:
            return

        tenant_id = getattr(self.orchestrator, "tenant_id", "default")
        records = (
            await self.orchestrator.session.execute(
                select(BeliefRecord).where(BeliefRecord.tenant_id == tenant_id)
            )
        ).scalars().all()
        for belief in records:
            source_ids = set(belief.source_ids or [])
            if oldest_source in source_ids and newest_source not in source_ids:
                try:
                    await self.orchestrator.record_contradiction(
                        ContradictionRequest(
                            belief_graph_id=belief.graph_id,
                            description=(
                                f"LongMemEval KU: superseded by newer session {newest_source}"
                            ),
                            strong=True,
                        )
                    )
                except Exception:
                    continue

    async def answer(self, item: LongMemEvalItem) -> str:
        episodes = await retrieve_longmemeval_episodes(self.orchestrator, item)
        if episodes:
            memory_context = build_transcript_memory_context(
                episodes,
                question_date=item.question_date,
            )
            beliefs = await self.orchestrator.beliefs.list_beliefs(min_confidence=0.25)
            if beliefs:
                belief_lines = [
                    f"- {b.label} (confidence={b.confidence:.2f}, status={b.status})"
                    for b in beliefs[:8]
                ]
                memory_context += (
                    "\n\nTracked beliefs (secondary; prefer recent transcript if conflict):\n"
                    + "\n".join(belief_lines)
                )
            result = await self.orchestrator.ollama.reason(
                question=item.question,
                memory_context=memory_context,
                extra_context={
                    "mode": "longmemeval_transcript_first",
                    "question_date": item.question_date,
                },
            )
            return str(result["answer"])

        qr = await self.orchestrator.query(
            QueryRequest(question=item.question, challenge=False)
        )
        return str(qr.answer)


class RAGLongMemEvalBackend:
    name: SystemName = "rag"

    def __init__(self, runner: RAGBaselineRunner) -> None:
        self.runner = runner

    async def reset(self) -> None:
        self.runner.memory.episodes.clear()

    async def ingest_item(self, item: LongMemEvalItem) -> None:
        for session_id, session_date, turns in zip(
            item.haystack_session_ids,
            item.haystack_dates,
            item.haystack_sessions,
            strict=False,
        ):
            content = format_session_content(session_id, session_date, turns)
            await self.runner.ingest(content)

    async def answer(self, item: LongMemEvalItem) -> str:
        return str(await self.runner.query(item.question))


class MemGPTLongMemEvalBackend:
    name: SystemName = "memgpt"

    def __init__(self, runner: MemGPTBaselineRunner) -> None:
        self.runner = runner

    async def reset(self) -> None:
        self.runner.memory = _MemGPTMemory()

    async def ingest_item(self, item: LongMemEvalItem) -> None:
        for session_id, session_date, turns in zip(
            item.haystack_session_ids,
            item.haystack_dates,
            item.haystack_sessions,
            strict=False,
        ):
            content = format_session_content(session_id, session_date, turns)
            await self.runner.ingest(content)

    async def answer(self, item: LongMemEvalItem) -> str:
        return str(await self.runner.query(item.question))


def _aggregate_by_type(results: list[LongMemEvalItemResult]) -> tuple[float, dict[str, float], dict[str, int]]:
    if not results:
        return 0.0, {}, {}

    overall = sum(1.0 if r.correct else 0.0 for r in results) / len(results)
    by_type: dict[str, list[float]] = {}
    for r in results:
        qtype = "abstention" if r.question_id.endswith("_abs") else r.question_type
        by_type.setdefault(qtype, []).append(1.0 if r.correct else 0.0)

    accuracy_by_type = {k: round(sum(v) / len(v), 4) for k, v in sorted(by_type.items())}
    counts = {k: len(v) for k, v in sorted(by_type.items())}
    return round(overall, 4), accuracy_by_type, counts


async def run_longmemeval(
    backend: LongMemEvalMemoryBackend,
    items: list[LongMemEvalItem],
    *,
    llm_judge: BaseLLMClient | None,
    dataset_path: str | Path,
    use_llm_judge: bool = True,
) -> LongMemEvalRunResult:
    results: list[LongMemEvalItemResult] = []

    for item in items:
        try:
            await backend.reset()
            await backend.ingest_item(item)
            hypothesis = await backend.answer(item)
            correct, judge_response = await judge_longmemeval_answer(
                llm_judge,
                item,
                hypothesis,
                use_llm_judge=use_llm_judge,
            )
            results.append(
                LongMemEvalItemResult(
                    question_id=item.question_id,
                    question_type=item.question_type,
                    question=item.question,
                    expected_answer=item.answer,
                    hypothesis=hypothesis,
                    correct=correct,
                    judge_response=judge_response,
                )
            )
        except Exception as exc:
            results.append(
                LongMemEvalItemResult(
                    question_id=item.question_id,
                    question_type=item.question_type,
                    question=item.question,
                    expected_answer=item.answer,
                    hypothesis="",
                    correct=False,
                    judge_response="error",
                    error=str(exc),
                )
            )

    accuracy, by_type, counts = _aggregate_by_type(results)
    return LongMemEvalRunResult(
        system=backend.name,
        dataset_path=str(dataset_path),
        items_run=len(results),
        accuracy=accuracy,
        accuracy_by_type=by_type,
        item_counts_by_type=counts,
        results=results,
        judge="longmemeval_official_prompt" if use_llm_judge else "deterministic",
    )


async def run_longmemeval_comparison(
    backends: list[LongMemEvalMemoryBackend],
    *,
    dataset_path: str | Path | None = None,
    question_types: list[str] | None = None,
    limit: int | None = None,
    offset: int = 0,
    llm_judge: BaseLLMClient | None = None,
    use_llm_judge: bool = True,
) -> dict[str, Any]:
    path = Path(dataset_path) if dataset_path else default_dataset_path()
    items = load_longmemeval_dataset(
        path,
        question_types=question_types,
        limit=limit,
        offset=offset,
    )
    runs: dict[str, LongMemEvalRunResult] = {}
    for backend in backends:
        runs[backend.name] = await run_longmemeval(
            backend,
            items,
            llm_judge=llm_judge,
            dataset_path=path,
            use_llm_judge=use_llm_judge,
        )

    return {
        "dataset": str(path),
        "items_run": len(items),
        "question_types_filter": question_types,
        "runs": {name: run.to_dict() for name, run in runs.items()},
        "summary_table": [
            {
                "system": name,
                "accuracy": run.accuracy,
                "by_type": run.accuracy_by_type,
            }
            for name, run in runs.items()
        ],
    }
