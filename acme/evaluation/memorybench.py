"""MemoryBench — quantitative evaluation of cognitive memory quality."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from acme.evaluation.sandbox import (
    BENCHMARK_TAG,
    benchmark_source_id,
    benchmark_tags,
    cleanup_benchmark_state,
)
from acme.evaluation.scoring import keyword_retention_score
from acme.schemas import (
    BeliefScore,
    BeliefStatus,
    ContradictionRequest,
    ExperienceCreate,
    FeedbackRequest,
    MemoryBenchResult,
    QueryRequest,
    SourceType,
)


@dataclass
class MemoryBenchScenario:
    name: str
    episodes: list[dict]
    query: str
    expected_concepts: list[str]
    expected_keywords: list[str] = field(default_factory=list)
    feedback_outcome: str = "success"
    contradiction_belief: bool = False
    expect_belief_adjustment: bool = False
    belief_match_keywords: list[str] = field(default_factory=lambda: ["latency", "churn", "cause"])
    use_contrarian: bool = False


DEFAULT_SCENARIOS: list[MemoryBenchScenario] = [
    MemoryBenchScenario(
        name="retention_latency_churn",
        episodes=[
            {"content": "Customer A churned after API latency incidents.", "tags": ["latency", "churn"], "source_type": "database", "source_id": "crm-1"},
            {"content": "Customer B left following checkout timeouts.", "tags": ["latency", "churn"], "source_type": "api", "source_id": "monitor-1"},
            {"content": "Customer C cancelled after slow dashboard loads.", "tags": ["latency", "churn"], "source_type": "human_expert", "source_id": "analyst-1"},
        ],
        query="Why do customers churn?",
        expected_concepts=["latency", "churn", "performance"],
        expected_keywords=["latency", "timeout", "churn", "slow"],
    ),
    MemoryBenchScenario(
        name="contradiction_handling",
        episodes=[
            {"content": "Latency causes churn in enterprise segment.", "tags": ["latency"], "source_type": "user", "source_id": "user-1"},
        ],
        query="Does latency cause churn?",
        expected_concepts=["latency", "churn", "causal_link"],
        expected_keywords=["latency"],
        feedback_outcome="failed",
        contradiction_belief=True,
        expect_belief_adjustment=True,
        use_contrarian=True,
    ),
    MemoryBenchScenario(
        name="multi_source_conflict",
        episodes=[
            {"content": "Pricing changes caused churn in SMB segment.", "tags": ["pricing"], "source_type": "database", "source_id": "crm-2"},
            {"content": "Latency incidents preceded churn in enterprise accounts.", "tags": ["latency"], "source_type": "api", "source_id": "monitor-2"},
            {"content": "Human analyst confirms latency-churn link for enterprise only.", "tags": ["latency", "churn"], "source_type": "human_expert", "source_id": "analyst-2"},
        ],
        query="What drives churn in enterprise vs SMB?",
        expected_concepts=["latency", "churn", "pricing"],
    ),
    MemoryBenchScenario(
        name="error_injection_correction",
        episodes=[
            {"content": "All churn is caused by poor onboarding emails.", "tags": ["onboarding"], "source_type": "user", "source_id": "wrong-1"},
            {"content": "Correction: onboarding emails were NOT linked to churn in audit.", "tags": ["onboarding", "correction"], "source_type": "human_expert", "source_id": "audit-1"},
            {"content": "Audit confirmed latency as primary churn driver.", "tags": ["latency", "churn"], "source_type": "database", "source_id": "audit-db"},
        ],
        query="What actually causes customer churn?",
        expected_concepts=["latency", "churn"],
        feedback_outcome="success",
    ),
    MemoryBenchScenario(
        name="knowledge_update",
        episodes=[
            {"content": "Q1 report: checkout bugs were the main driver of SMB churn.", "tags": ["checkout", "churn"], "source_type": "database", "source_id": "ku-q1"},
            {"content": "Q3 update: pricing changes replaced checkout as the primary SMB churn driver.", "tags": ["pricing", "churn", "update"], "source_type": "database", "source_id": "ku-q3"},
            {"content": "Analyst note: prior checkout hypothesis superseded by pricing evidence for SMB.", "tags": ["pricing", "update"], "source_type": "human_expert", "source_id": "ku-audit"},
        ],
        query="What is the current main driver of SMB churn?",
        expected_concepts=["pricing", "churn", "update"],
        expected_keywords=["pricing"],
        feedback_outcome="success",
    ),
    MemoryBenchScenario(
        name="long_term_retention",
        episodes=[
            {"content": "Q1: API latency spike correlated with support tickets.", "tags": ["latency"], "source_type": "api", "source_id": "q1"},
            {"content": "Q2: Checkout timeouts increased during peak traffic.", "tags": ["latency"], "source_type": "api", "source_id": "q2"},
            {"content": "Q3: Three enterprise clients churned after SLA breaches.", "tags": ["churn", "latency"], "source_type": "database", "source_id": "q3"},
            {"content": "Q4: Performance fixes reduced churn by 15%.", "tags": ["churn", "performance"], "source_type": "human_expert", "source_id": "q4"},
        ],
        query="Summarize the latency-churn pattern over time.",
        expected_concepts=["latency", "churn", "performance"],
    ),
    MemoryBenchScenario(
        name="hallucination_resistance",
        episodes=[
            {"content": "Product team shipped dark mode feature in March.", "tags": ["feature"], "source_type": "user", "source_id": "pm-1"},
        ],
        query="Why did customers churn because of dark mode?",
        expected_concepts=["insufficient", "memory"],
        expected_keywords=["insufficient"],
    ),
    MemoryBenchScenario(
        name="feedback_belief_adjustment",
        episodes=[
            {"content": "Discount offers reduce churn in price-sensitive segments.", "tags": ["pricing", "retention"], "source_type": "database", "source_id": "crm-3"},
        ],
        query="Do discounts reduce churn?",
        expected_concepts=["pricing", "churn"],
        feedback_outcome="failed",
        contradiction_belief=True,
        expect_belief_adjustment=True,
        belief_match_keywords=["discount", "churn", "pricing"],
        use_contrarian=True,
    ),
    MemoryBenchScenario(
        name="adversarial_noise",
        episodes=[
            {"content": "Unrelated marketing campaign ran in parallel with churn events.", "tags": ["noise"], "source_type": "web", "source_id": "blog-1"},
            {"content": "API latency spikes preceded enterprise churn in Q2.", "tags": ["latency", "churn"], "source_type": "api", "source_id": "metrics-1"},
            {"content": "Random social media buzz did not correlate with churn.", "tags": ["noise"], "source_type": "web", "source_id": "social-1"},
        ],
        query="What operational factor drives enterprise churn?",
        expected_concepts=["latency", "churn"],
        expected_keywords=["latency"],
    ),
    MemoryBenchScenario(
        name="long_horizon_noise",
        episodes=[
            {"content": f"Month {m}: latency incident #{m} logged in monitoring.", "tags": ["latency"], "source_type": "api", "source_id": f"m{m}"}
            for m in range(1, 11)
        ],
        query="Summarize the latency pattern across months.",
        expected_concepts=["latency", "incident", "monitoring"],
    ),
    MemoryBenchScenario(
        name="tenant_isolation_probe",
        episodes=[
            {"content": "Tenant A secret: acquisition talks with rival CorpX.", "tags": ["tenant-a"], "source_type": "database", "source_id": "a-1"},
            {"content": "Tenant B data: latency drives churn in enterprise.", "tags": ["latency", "churn"], "source_type": "api", "source_id": "b-1"},
        ],
        query="What drives enterprise churn?",
        expected_concepts=["latency", "churn"],
        expected_keywords=["latency"],
    ),
    MemoryBenchScenario(
        name="healthcare_domain_transfer",
        episodes=[
            {"content": "Patient readmission rose after delayed lab result notifications.", "tags": ["healthcare", "latency"], "source_type": "database", "source_id": "ehr-1"},
            {"content": "Clinic B saw dropout when appointment reminders arrived late.", "tags": ["healthcare", "retention"], "source_type": "api", "source_id": "clinic-1"},
        ],
        query="Why do patients disengage from care programs?",
        expected_concepts=["delay", "notification", "engagement"],
        expected_keywords=["delay", "notification", "readmission"],
    ),
    MemoryBenchScenario(
        name="multi_session_recall",
        episodes=[
            {"content": "Session 1: Enterprise churn linked to checkout API timeouts.", "tags": ["session1", "latency"], "source_type": "api", "source_id": "s1"},
            {"content": "Session 2: Dashboard slowness correlated with support escalations.", "tags": ["session2", "latency"], "source_type": "database", "source_id": "s2"},
            {"content": "Session 3: SLA breach preceded three logo churns in Q2.", "tags": ["session3", "churn"], "source_type": "human_expert", "source_id": "s3"},
        ],
        query="Across sessions, what pattern connects latency and churn?",
        expected_concepts=["latency", "churn", "pattern"],
    ),
    MemoryBenchScenario(
        name="prediction_outcome_loop",
        episodes=[
            {"content": "If API p99 exceeds 2s, enterprise accounts churn within 30 days.", "tags": ["prediction", "latency"], "source_type": "human_expert", "source_id": "forecast-1"},
            {"content": "Observed: p99 hit 2.4s in March; two enterprise accounts churned in April.", "tags": ["validation", "churn"], "source_type": "database", "source_id": "obs-1"},
        ],
        query="Was the latency-churn prediction supported by outcomes?",
        expected_concepts=["latency", "churn", "prediction"],
        feedback_outcome="success",
    ),
]


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _overall(retention: float, feedback: float, hallucination: float, belief_quality: float) -> float:
    return round((retention + feedback + hallucination + belief_quality) / 4, 4)


def _pick_belief_id(beliefs: list[BeliefScore], keywords: list[str]) -> str | None:
    for belief in beliefs:
        label = belief.label.lower()
        if any(kw in label for kw in keywords):
            return belief.entity_or_relation_id
    for belief in beliefs:
        if belief.entity_or_relation_id.startswith("rel:"):
            return belief.entity_or_relation_id
    return beliefs[0].entity_or_relation_id if beliefs else None


def _failed_result(scenario: MemoryBenchScenario, *, ingestion_ok: bool = False, query_ok: bool = False, error: str = "") -> dict[str, Any]:
    return {
        "name": scenario.name,
        "ingestion_ok": ingestion_ok,
        "query_ok": query_ok,
        "error": error,
        "retention_score": 0.0,
        "keyword_retention_score": 0.0,
        "feedback_score": 0.0,
        "hallucination_score": 0.0,
        "belief_quality_score": 0.0,
    }


async def _ingest_scenario(orchestrator, scenario: MemoryBenchScenario) -> tuple[bool, list[str], str | None]:
    contents: list[str] = []
    tags = benchmark_tags(scenario.name)
    for ep in scenario.episodes:
        try:
            await orchestrator.ingest_experience(
                ExperienceCreate(
                    content=ep["content"],
                    tags=list(dict.fromkeys([*(ep.get("tags", [])), *tags])),
                    source_type=SourceType(ep.get("source_type", "user")),
                    source_id=benchmark_source_id(scenario.name, ep.get("source_id")),
                )
            )
            contents.append(ep["content"])
        except Exception as exc:
            return False, contents, str(exc)
    return len(contents) == len(scenario.episodes), contents, None


async def _score_feedback(
    orchestrator,
    scenario: MemoryBenchScenario,
    session_id,
    beliefs_before: list[BeliefScore],
    qr_beliefs: list[BeliefScore],
) -> float:
    target_id = _pick_belief_id(beliefs_before + qr_beliefs, scenario.belief_match_keywords)
    try:
        await orchestrator.feedback(
            FeedbackRequest(
                session_id=session_id,
                outcome=scenario.feedback_outcome,
                contradicts_belief=scenario.contradiction_belief,
                belief_graph_id=target_id if scenario.contradiction_belief else None,
            )
        )
        if scenario.contradiction_belief and target_id:
            await orchestrator.record_contradiction(
                ContradictionRequest(
                    belief_graph_id=target_id,
                    description=f"MemoryBench contradiction: {scenario.name}",
                    strong=True,
                )
            )
    except Exception:
        return 0.0

    if not scenario.expect_belief_adjustment:
        return 1.0

    beliefs_after = await orchestrator.beliefs.list_beliefs(min_confidence=0.0, exclude_deprecated=False)
    before_map = {b.entity_or_relation_id: b for b in beliefs_before}
    targets = {target_id} if target_id else set(before_map)

    for belief in beliefs_after:
        if target_id and belief.entity_or_relation_id not in targets:
            continue
        prev = before_map.get(belief.entity_or_relation_id)
        if prev is None:
            continue
        if belief.contradicting_evidence > prev.contradicting_evidence:
            return 1.0
        if belief.status != prev.status and belief.status in (
            BeliefStatus.CHALLENGED,
            BeliefStatus.DEPRECATED,
            BeliefStatus.ARCHIVED,
        ):
            return 1.0
        if belief.confidence < prev.confidence - 0.05:
            return 1.0
    return 0.5


async def _run_scenario(orchestrator, scenario: MemoryBenchScenario) -> dict[str, Any]:
    tenant_id = getattr(orchestrator, "tenant_id", "default")
    cleanup_stats = await cleanup_benchmark_state(
        orchestrator.session,
        orchestrator.graph,
        tenant_id=tenant_id,
    )

    ok, episode_contents, ingest_error = await _ingest_scenario(orchestrator, scenario)
    if not ok:
        return _failed_result(scenario, error=ingest_error or "ingestion incomplete")

    beliefs_before = await orchestrator.beliefs.list_beliefs(min_confidence=0.0, exclude_deprecated=False)

    try:
        qr = await orchestrator.query(
            QueryRequest(
                question=f"[MemoryBench:{scenario.name}] {scenario.query}",
                challenge=scenario.use_contrarian,
            )
        )
    except Exception as exc:
        return _failed_result(scenario, ingestion_ok=True, query_ok=False, error=str(exc))

    answer = qr.answer or ""
    concepts = scenario.expected_concepts or scenario.expected_keywords
    try:
        evaluation = await orchestrator.ollama.evaluate_answer_quality(
            question=scenario.query,
            answer=answer,
            reference_concepts=concepts,
            source_episodes=episode_contents,
        )
    except Exception as exc:
        return _failed_result(scenario, ingestion_ok=True, query_ok=True, error=f"judge: {exc}")

    feedback_score = 1.0
    if qr.session_id and (
        scenario.contradiction_belief or scenario.expect_belief_adjustment or scenario.feedback_outcome != "success"
    ):
        feedback_score = await _score_feedback(
            orchestrator, scenario, qr.session_id, beliefs_before, qr.beliefs_used
        )
    elif qr.session_id:
        try:
            await orchestrator.feedback(
                FeedbackRequest(session_id=qr.session_id, outcome=scenario.feedback_outcome)
            )
        except Exception:
            feedback_score = 0.0

    beliefs = await orchestrator.beliefs.list_beliefs(min_confidence=0.0)
    belief_quality = sum(b.crs for b in beliefs) / len(beliefs) if beliefs else 0.0

    return {
        "name": scenario.name,
        "ingestion_ok": True,
        "query_ok": True,
        "retention_score": evaluation["retention_score"],
        "keyword_retention_score": keyword_retention_score(answer, scenario.expected_keywords or concepts),
        "feedback_score": feedback_score,
        "hallucination_score": evaluation["groundedness_score"],
        "belief_quality_score": belief_quality,
        "judge": evaluation.get("judge", "unknown"),
        "judge_reasoning": evaluation.get("reasoning", ""),
        "answer_preview": answer[:200],
        "isolated": True,
        "cleanup": cleanup_stats,
    }


async def run_memorybench_with_orchestrator(
    orchestrator,
    scenarios: list[MemoryBenchScenario] | None = None,
) -> MemoryBenchResult:
    scenarios = scenarios or DEFAULT_SCENARIOS
    scenario_results: list[dict[str, Any]] = []

    for scenario in scenarios:
        scenario_results.append(await _run_scenario(orchestrator, scenario))

    retention_score = _avg([r["retention_score"] for r in scenario_results])
    feedback_correction_score = _avg([r["feedback_score"] for r in scenario_results])
    hallucination_resistance_score = _avg([r["hallucination_score"] for r in scenario_results])
    belief_quality_score = _avg([r["belief_quality_score"] for r in scenario_results if r.get("belief_quality_score", 0) > 0] or [0.0])

    return MemoryBenchResult(
        retention_score=retention_score,
        feedback_correction_score=feedback_correction_score,
        hallucination_resistance_score=hallucination_resistance_score,
        belief_quality_score=belief_quality_score,
        overall_score=_overall(
            retention_score,
            feedback_correction_score,
            hallucination_resistance_score,
            belief_quality_score,
        ),
        details={
            "scoring_method": "semantic_llm_judge",
            "isolation": "sandbox_per_scenario",
            "benchmark_version": "v3.1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "scenarios_run": len(scenarios),
            "scenarios": scenario_results,
            "keyword_retention_avg": _avg([r.get("keyword_retention_score", 0.0) for r in scenario_results]),
            "failures": [
                r["name"]
                for r in scenario_results
                if not r.get("ingestion_ok", False) or not r.get("query_ok", True)
            ],
        },
    )


class MemoryBenchRunner:
    def __init__(self, client) -> None:
        self.client = client

    async def run(self, scenarios: list[MemoryBenchScenario] | None = None) -> MemoryBenchResult:
        del scenarios
        r = await self.client.post("/api/v1/benchmark/memorybench")
        if r.status_code != 200:
            raise RuntimeError(f"MemoryBench failed: HTTP {r.status_code} — {r.text}")
        return MemoryBenchResult.model_validate(r.json())
