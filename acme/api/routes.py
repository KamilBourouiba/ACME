from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from acme import __version__
from acme.db.session import get_session
from acme.config import settings
from acme.graph.neo4j_client import neo4j_client
from acme.llm.factory import llm_client
from acme.middleware.rate_limit import check_benchmark_rate_limit
from acme.middleware.tenant import verify_api_key
from acme.observability.metrics import collect_metrics
from acme.observability.runtime_stats import snapshot as runtime_snapshot
from acme.orchestrator import ACMEOrchestrator
from acme.schemas import (
    AbstractionResponse,
    BeliefScore,
    CompressionRequest,
    CompressionResponse,
    EpisodeMemoryStatus,
    BenchmarkComparisonResult,
    CausalValidateRequest,
    CausalValidateResponse,
    ConsolidationResponse,
    ContradictionRequest,
    ExperienceCreate,
    ExperienceResponse,
    FeedbackRequest,
    FeedbackResponse,
    ForgettingRequest,
    ForgettingResponse,
    HealthResponse,
    HypothesisResponse,
    LearningRequest,
    LearningResponse,
    MemoryBenchResult,
    MemoryTier,
    PredictionCreate,
    PredictionResponse,
    PredictionValidate,
    QueryRequest,
    QueryResponse,
)

router = APIRouter()


def get_orchestrator(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ACMEOrchestrator:
    tenant_id = getattr(request.state, "tenant_id", settings.default_tenant_id)
    return ACMEOrchestrator(
        session=session,
        graph=neo4j_client,
        ollama=llm_client,
        tenant_id=tenant_id,
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    postgres_ok = True
    try:
        from acme.db.session import engine

        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        postgres_ok = False

    neo4j_ok = await neo4j_client.ping()
    llm_ok = await llm_client.ping()

    status = "healthy" if all([postgres_ok, neo4j_ok]) else "degraded"
    return HealthResponse(
        status=status,
        postgres=postgres_ok,
        neo4j=neo4j_ok,
        llm=llm_ok,
        llm_provider=settings.llm_provider,
        version=__version__,
    )


@router.post("/experiences", response_model=ExperienceResponse, status_code=201)
async def ingest_experience(
    data: ExperienceCreate,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> ExperienceResponse:
    return await orchestrator.ingest_experience(data)


@router.post("/query", response_model=QueryResponse)
async def query_memory(
    data: QueryRequest,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    return await orchestrator.query(data)


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    data: FeedbackRequest,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> FeedbackResponse:
    try:
        return await orchestrator.feedback(data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/beliefs", response_model=list[BeliefScore])
async def list_beliefs(
    min_confidence: float = 0.0,
    session: AsyncSession = Depends(get_session),
) -> list[BeliefScore]:
    from acme.engines.belief import BeliefEngine

    engine = BeliefEngine(session)
    return await engine.list_beliefs(min_confidence=min_confidence)


@router.post("/compress", response_model=CompressionResponse)
async def compress_episodes(
    data: CompressionRequest,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> CompressionResponse:
    return await orchestrator.compress(data)


@router.get("/abstractions", response_model=list[AbstractionResponse])
async def list_abstractions(
    min_confidence: float = 0.0,
    session: AsyncSession = Depends(get_session),
) -> list[AbstractionResponse]:
    from acme.config import settings
    from acme.engines.compression import CompressionEngine
    from acme.graph.neo4j_client import neo4j_client
    from acme.llm.factory import llm_client

    engine = CompressionEngine(session, neo4j_client, llm_client)
    return await engine.list_abstractions(min_confidence=min_confidence)


@router.post("/forget/run", response_model=ForgettingResponse)
async def run_forgetting(
    data: ForgettingRequest,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> ForgettingResponse:
    return await orchestrator.run_forgetting(data)


@router.get("/episodes", response_model=list[EpisodeMemoryStatus])
async def list_episodes(
    tier: MemoryTier | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[EpisodeMemoryStatus]:
    from acme.engines.forgetting import ForgettingEngine

    engine = ForgettingEngine(session)
    return await engine.list_episodes(tier=tier, limit=limit)


@router.post("/learn/run", response_model=LearningResponse)
async def run_learning(
    data: LearningRequest,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> LearningResponse:
    return await orchestrator.run_learning(data)


@router.get("/hypotheses", response_model=list[HypothesisResponse])
async def list_hypotheses(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[HypothesisResponse]:
    from acme.engines.learning import LearningEngine
    from acme.graph.neo4j_client import neo4j_client
    from acme.llm.factory import llm_client

    engine = LearningEngine(session, neo4j_client, llm_client)
    return await engine.list_hypotheses(limit=limit)


@router.get("/learn/cycles")
async def list_learning_cycles(
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    from acme.engines.learning import LearningEngine
    from acme.graph.neo4j_client import neo4j_client
    from acme.llm.factory import llm_client

    engine = LearningEngine(session, neo4j_client, llm_client)
    return await engine.list_cycles(limit=limit)


@router.post("/predictions", response_model=PredictionResponse, status_code=201)
async def create_prediction(
    data: PredictionCreate,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> PredictionResponse:
    return await orchestrator.create_prediction(data)


@router.post("/predictions/validate", response_model=PredictionResponse)
async def validate_prediction(
    data: PredictionValidate,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> PredictionResponse:
    try:
        return await orchestrator.validate_prediction(data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/predictions", response_model=list[PredictionResponse])
async def list_predictions(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[PredictionResponse]:
    from acme.engines.prediction import PredictionEngine

    engine = PredictionEngine(session)
    return await engine.list_predictions(limit=limit)


@router.post("/contradictions")
async def record_contradiction(
    data: ContradictionRequest,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> dict:
    try:
        return await orchestrator.record_contradiction(data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/meta-learning")
async def get_meta_learning(
    session: AsyncSession = Depends(get_session),
) -> dict:
    from acme.engines.meta_learning import MetaLearningEngine

    engine = MetaLearningEngine(session)
    return await engine.snapshot()


@router.get("/metrics")
async def get_metrics(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    tenant_id = getattr(request.state, "tenant_id", settings.default_tenant_id)
    base = await collect_metrics(session, tenant_id=tenant_id)
    base["runtime"] = runtime_snapshot()
    base["ablation"] = {
        "disable_contrarian": settings.ablation_disable_contrarian,
        "disable_belief_sync": settings.ablation_disable_belief_sync,
        "disable_vector": settings.ablation_disable_vector,
    }
    return base


@router.post("/benchmark/memorybench", response_model=MemoryBenchResult)
async def run_memorybench(
    request: Request,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> MemoryBenchResult:
    verify_api_key(request)
    check_benchmark_rate_limit(request)
    from acme.evaluation.memorybench import run_memorybench_with_orchestrator
    from acme.evaluation.benchmark_store import save_memorybench_run

    tenant_id = getattr(request.state, "tenant_id", settings.default_tenant_id)
    result = await run_memorybench_with_orchestrator(orchestrator)
    await save_memorybench_run(orchestrator.session, result, tenant_id=tenant_id)
    return result


@router.post("/benchmark/compare", response_model=BenchmarkComparisonResult)
async def run_benchmark_comparison(
    request: Request,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> BenchmarkComparisonResult:
    verify_api_key(request)
    check_benchmark_rate_limit(request)
    from acme.evaluation.compare_mutex import CompareAlreadyRunningError

    try:
        return await orchestrator.run_benchmark_comparison()
    except CompareAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/benchmark/compare/async")
async def run_benchmark_comparison_async(request: Request) -> dict:
    """Start compare in background — poll GET /benchmark/compare/jobs/{job_id}."""
    verify_api_key(request)
    check_benchmark_rate_limit(request)
    from acme.evaluation.benchmark_jobs import start_compare_job
    from acme.evaluation.compare_mutex import CompareAlreadyRunningError

    tenant_id = getattr(request.state, "tenant_id", settings.default_tenant_id)
    try:
        job_id = await start_compare_job(tenant_id=tenant_id)
    except CompareAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "job_id": job_id,
        "status": "running",
        "poll_url": f"/api/v1/benchmark/compare/jobs/{job_id}",
    }


@router.get("/benchmark/compare/jobs/{job_id}")
async def get_benchmark_compare_job(job_id: str, request: Request) -> dict:
    verify_api_key(request)
    from acme.evaluation.benchmark_jobs import get_job

    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/benchmark/compare/jobs")
async def list_benchmark_compare_jobs(request: Request, limit: int = 20) -> dict:
    verify_api_key(request)
    from acme.evaluation.benchmark_jobs import list_jobs

    return {"jobs": list_jobs(limit=limit)}


@router.get("/benchmark/runs/latest")
async def get_latest_benchmark_run(
    request: Request,
    session: AsyncSession = Depends(get_session),
    run_type: str | None = None,
) -> dict:
    from acme.evaluation.benchmark_store import get_latest_run, record_to_dict

    tenant_id = getattr(request.state, "tenant_id", settings.default_tenant_id)
    record = await get_latest_run(session, run_type=run_type, tenant_id=tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No benchmark runs found")
    return record_to_dict(record)


@router.get("/benchmark/export")
async def export_last_benchmark(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    verify_api_key(request)
    from acme.evaluation.benchmark_store import get_latest_run

    tenant_id = getattr(request.state, "tenant_id", settings.default_tenant_id)
    record = await get_latest_run(session, run_type="compare", tenant_id=tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No compare run stored — run /benchmark/compare first")
    export = record.payload.get("export") if isinstance(record.payload, dict) else None
    if export:
        return export
    return record.payload


@router.post("/causal/validate", response_model=CausalValidateResponse)
async def validate_causal_intervention(
    data: CausalValidateRequest,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> CausalValidateResponse:
    return await orchestrator.validate_causal_intervention(data)


@router.post("/consolidation/run", response_model=ConsolidationResponse)
async def run_consolidation(
    data: LearningRequest,
    orchestrator: ACMEOrchestrator = Depends(get_orchestrator),
) -> ConsolidationResponse:
    return await orchestrator.run_consolidation(data)


@router.get("/graph/entities/{name}")
async def get_entity_neighborhood(name: str, request: Request) -> dict:
    tenant_id = getattr(request.state, "tenant_id", settings.default_tenant_id)
    entities = await neo4j_client.search_entities([name], limit=1, tenant_id=tenant_id)
    neighborhood = await neo4j_client.get_neighborhood(name, tenant_id=tenant_id)
    return {"entity": entities[0] if entities else None, "neighborhood": neighborhood, "tenant_id": tenant_id}


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: UUID,
    db: AsyncSession = Depends(get_session),
) -> dict:
    from sqlalchemy import select

    from acme.db.models import QuerySession

    stmt = select(QuerySession).where(QuerySession.id == session_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": str(record.id),
        "question": record.question,
        "answer": record.answer,
        "confidence": record.confidence,
        "reasoning": record.reasoning,
        "outcome": record.outcome,
        "feedback": record.feedback,
        "created_at": record.created_at.isoformat(),
    }
